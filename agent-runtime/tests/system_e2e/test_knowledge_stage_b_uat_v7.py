"""Non-live checks for the seven-case authorization and bounded evidence reuse."""
from copy import deepcopy
import json

import pytest

from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e import knowledge_stage_b_uat_v7 as new
from tests.system_e2e import test_knowledge_stage_b_uat_v4 as budget_checks
from tests.system_e2e import test_knowledge_stage_b_uat_v6 as verdict_checks


def compatible_manifest():
    value, _ = new.run06_assets()
    for name in new.COMPATIBLE_CHANGES:
        value["assets"][name] = old.digest((old.REPO / name).read_bytes())
    return value


def test_scope_and_cumulative_ledger_restore_on_cancel():
    before = old.RUN_ID, old.CASES, old.LIMITS, old.Budget, old.prepare, v2.TOTAL_LIMITS, v2.prompt_hashes
    with pytest.raises(KeyboardInterrupt), new.run_07_bindings():
        assert old.CASES == new.FULL_CASES[3:] and len(old.CASES) == 7
        assert old.RUN_ID == new.RUN_ID and old.LIMITS == new.LIMITS
        rows = new.prior_bindings()
        assert len(rows) == 6
        names = ("e2e", "model", "search", "embedding", "rerank")
        assert [sum(row["calls"][key] for row in rows) for key in names] == [14, 34, 21, 11, 11]
        assert [sum(row["calls"][key] for row in rows) + old.LIMITS[key] for key in names] == [21, 55, 49, 25, 25]
        assert v2.TOTAL_LIMITS["e2e"] == 21 and v2.TOTAL_LIMITS["model"] == 60
        raise KeyboardInterrupt
    assert (old.RUN_ID, old.CASES, old.LIMITS, old.Budget, old.prepare, v2.TOTAL_LIMITS, v2.prompt_hashes) == before


@pytest.mark.parametrize("count", [True, -1, 35, 1.0])
def test_invalid_or_excess_prior_budget_rejected(monkeypatch, count):
    rows = new.previous.prior_bindings()
    rows[0]["calls"]["model"] = count
    monkeypatch.setattr(new.previous, "prior_bindings", lambda: rows)
    with pytest.raises(ValueError, match="cumulative_budget_invalid"):
        new.prior_bindings()


def test_prior_hash_drift_rejected(monkeypatch):
    monkeypatch.setattr(new, "RUN06_HASHES", {**new.RUN06_HASHES, "result.json": "0" * 64})
    with pytest.raises(ValueError, match="prior_run_changed"):
        new.prior_bindings()


def test_exact_approved_production_difference_and_three_passed_sources():
    value = compatible_manifest()
    new.validate_reuse(value)
    assert new.REUSED_EVIDENCE["caseIds"] == ["UAT-KB-001", "UAT-KB-015a", "UAT-KB-004"]
    assert [item["caseId"] for item in new.CASES] == [
        "UAT-KB-002", "UAT-KB-003", "UAT-KB-005", "UAT-KB-006", "UAT-KB-015b", "UAT-KB-016", "UAT-KB-008"]


@pytest.mark.parametrize("key", ["environment", "indexBinding", "taskVersions", "promptHashes", "gold", "evaluation", "executables"])
def test_reuse_snapshot_drift_is_not_ignored(key):
    value = compatible_manifest()
    value[key] = {}
    with pytest.raises(ValueError, match="reuse_snapshot_changed"):
        new.validate_reuse(value)


@pytest.mark.parametrize("change", ["missing", "extra", "wrong_hash", "unapproved_guard"])
def test_production_asset_drift_rejected(change):
    value = compatible_manifest()
    key = new.COMPATIBLE_CHANGES[0]
    if change == "missing":
        del value["assets"][key]
    elif change == "extra":
        value["assets"]["agent-runtime/src/unapproved.py"] = "0" * 64
    elif change == "unapproved_guard":
        old_value, _ = new.run06_assets()
        value["assets"][key] = old_value["assets"][key]
    else:
        value["assets"][key] = "0" * 64
    with pytest.raises(ValueError, match="reuse_source_changed"):
        new.validate_reuse(value)


@pytest.fixture
def manifest_root(tmp_path, monkeypatch):
    value = compatible_manifest()
    value.update(frozenHead="a" * 40, cases=new.CASES, limits=new.LIMITS)
    # Unit-isolate only the inherited filesystem scan; keep the actual historical
    # hashes, approved Git source blobs and new protocol validation exercised.
    monkeypatch.setattr(v2, "_prepare", lambda root: deepcopy(value))
    monkeypatch.setattr(old, "git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    def existing_validator(root, expected_sha):
        raw = (root / "manifest.json").read_bytes()
        if expected_sha is not None and old.digest(raw) != expected_sha:
            raise ValueError("stage_b.manifest_sha_mismatch")
        return json.loads(raw), old.digest(raw)
    monkeypatch.setattr(v2, "_validate", existing_validator)
    new.prepare(tmp_path)
    return tmp_path


def test_prepared_manifest_keeps_complete_gold_but_only_seven_new_cases(manifest_root):
    raw = (manifest_root / "manifest.json").read_bytes()
    value, sha = new.validate_manifest(manifest_root, old.digest(raw))
    assert value["schemaVersion"] == 7 and sha == old.digest(raw)
    assert value["cases"] == list(new.CASES) and value["gold"] == old.GOLD
    assert value["reusedEvidence"] == new.REUSED_EVIDENCE and len(value["priorRuns"]) == 6
    with pytest.raises(FileExistsError):
        new.prepare(manifest_root)
    with pytest.raises(ValueError, match="manifest_sha_mismatch"):
        new.validate_manifest(manifest_root, "0" * 64)


@pytest.mark.parametrize("key,value", [
    ("schemaVersion", True), ("schemaVersion", 7.0), ("priorRuns", []), ("cumulativeLimits", {"e2e": 20}),
    ("diagnosticVersion", "other"), ("downstreamDiagnosticVersion", "other"), ("authorizationReference", "old"),
    ("runRoot", "elsewhere"), ("taskVersions", {}), ("promptHashes", {}), ("qualityVersion", "old"),
    ("reusedEvidence", {}), ("cases", list(new.FULL_CASES)), ("cases", list(new.CASES)[::-1]),
    ("cases", [new.CASES[0]] * 7), ("cases", list(new.CASES)[:-1]),
    ("limits", {**new.LIMITS, "business": False}), ("limits", {**new.LIMITS, "model": 21.0}),
    ("extra", 1),
])
def test_manifest_protocol_tamper_rejected(manifest_root, key, value):
    path = manifest_root / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest[key] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="run_07_binding_invalid"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("raw", ['{"runId":"one","runId":"two"}', '{"limits":{"model":21,"model":22}}',
                                  '{"value":NaN}', '{"value":Infinity}', '[]', 'null'])
def test_duplicate_keys_and_nonfinite_rejected_before_old_loader(manifest_root, monkeypatch, raw):
    (manifest_root / "manifest.json").write_text(raw)
    monkeypatch.setattr(v2, "_validate", lambda *args: pytest.fail("must reject before inherited decode"))
    with pytest.raises(ValueError, match="manifest_json_invalid"):
        new.validate_manifest(manifest_root)


def test_inherited_frozen_asset_validation_is_still_required(manifest_root, monkeypatch):
    def reject(*args):
        raise ValueError("stage_b.frozen_asset_changed")
    monkeypatch.setattr(v2, "_validate", reject)
    with pytest.raises(ValueError, match="frozen_asset_changed"):
        new.validate_manifest(manifest_root)


@pytest.mark.parametrize("name", ["consumed.json", "journal.jsonl", "evidence.jsonl", "result.json"])
def test_consumption_or_partial_result_forbids_resume(manifest_root, name):
    (manifest_root / name).touch()
    with pytest.raises(ValueError, match="retry_resume_forbidden"):
        new.validate_manifest(manifest_root)


@pytest.fixture
def budget(tmp_path):
    with new.run_07_bindings():
        value = old.Budget(tmp_path, "a" * 64, lambda row: None)
        yield value
        value.journal.close()


@pytest.mark.asyncio
async def test_exact_seven_case_maximum_and_no_eighth_outbound(budget):
    for spec in new.CASES:
        budget.begin(spec)
        for task in ("action_selection", "knowledge_rewrite", "knowledge_summary"):
            await budget.model_request(verdict_checks.request(task, spec["question"]))
    assert budget.totals["e2e"] == 7 and budget.totals["model"] == 21
    with pytest.raises(ValueError):
        budget.begin(new.CASES[0])
    raw = (budget.root / "journal.jsonl").read_text()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 21 and {row["caseId"] for row in rows} == {spec["caseId"] for spec in new.CASES}
    assert not set(new.REUSED_EVIDENCE["caseIds"]) & {row["caseId"] for row in rows}
    assert all(spec["question"] not in raw for spec in new.CASES)
    assert json.loads((budget.root / "consumed.json").read_text())["runId"] == new.RUN_ID


@pytest.mark.asyncio
async def test_prompt_change_and_repeated_task_stop_zero_extra_calls(budget, monkeypatch):
    monkeypatch.setattr(budget_checks, "request", verdict_checks.request)
    await budget_checks.test_old_prompt_and_repeated_task_stop_before_outbound(budget)
    with pytest.raises(ValueError):
        budget.begin(new.CASES[1])
    assert budget.totals["e2e"] == 1 and budget.totals["model"] == 1


@pytest.mark.asyncio
async def test_other_endpoints_and_excess_search_remain_rejected(budget):
    await budget_checks.test_business_and_excess_search_forbidden(budget)


def test_reused_or_out_of_order_case_never_begins(budget):
    for spec in (new.FULL_CASES[0], new.CASES[1]):
        with pytest.raises(ValueError, match="case_order_invalid"):
            budget.begin(spec)
    assert budget.totals["e2e"] == 0 and budget.totals["model"] == 0


@pytest.mark.parametrize("spec", new.CASES, ids=lambda spec: spec["caseId"])
def test_original_gold_domain_and_failure_verdicts_unchanged(spec):
    verdict_checks.test_original_source_clause_verdict_and_quality_version(spec)
