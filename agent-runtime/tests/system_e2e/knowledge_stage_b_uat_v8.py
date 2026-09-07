"""One newly authorized ten-case run; current production, no historical replay."""
from __future__ import annotations

from contextlib import contextmanager
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

from agent_runtime.knowledge.contracts import KNOWLEDGE_QUALITY_VERSION_V3
from agent_runtime.knowledge.evidence import summary_task_v6 as summary
from agent_runtime.knowledge.evidence.builder import DeterministicEvidenceSelector
from agent_runtime.knowledge.rewrite_v7 import INSTRUCTION
from agent_runtime.model.deepseek.action_selector import ACTION_SELECTION_SYSTEM_INSTRUCTION
from tests.system_e2e import knowledge_stage_b_uat as legacy
from tests.system_e2e import knowledge_stage_b_uat_v2 as v2
from tests.system_e2e.knowledge_stage_b_uat_v7 import same_json, strict_json
from tests.system_e2e.knowledge_stage_b_cases import CASES, GOLD
from tests.system_e2e.knowledge_stage_b_citation_check_v2 import CHECK_VERSION, check_citations

RUN_ID = "knowledge-stage-b-uat-v8-20260907-run-08"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-08"
LIMITS = dict(e2e=10, model=30, search=40, embedding=20, rerank=40, business=0, retry=0, resume=0)
TOTAL_LIMITS = dict(e2e=25, model=67, search=80, embedding=40, rerank=52, business=0, retry=0, resume=0)
PER_CASE = dict(model=3, search=4, embedding=2, rerank=4, business=0)
TASKS = {"action_selection": "action-selection-v4", "knowledge_rewrite": "7", "knowledge_summary": "6"}
TOKENS = dict(action_selection=512, knowledge_rewrite=1536, knowledge_summary=1536)
_run_server = legacy.run_server
_budget = legacy.Budget
_services = legacy.local_services


def prompt_hashes():
    return {key: legacy.digest(value.encode()) for key, value in zip(TASKS,
        (ACTION_SELECTION_SYSTEM_INSTRUCTION, INSTRUCTION, summary.SUMMARY_PROMPT_V6), strict=True)}


def prior_bindings():
    rows = []
    for ordinal in range(1, 8):
        history = importlib.import_module(f"tests.system_e2e.test_knowledge_stage_b_run_{ordinal:02}_history")
        root = Path(__file__).with_name(f"knowledge_stage_b_run_{ordinal:02}")
        if any(legacy.digest((root / name).read_bytes()) != sha for name, sha in history.HASHES.items()):
            raise ValueError("stage_b.prior_run_changed")
        result = strict_json((root / "result.json").read_bytes())
        if result["status"] != "failed" or set(result["totals"]) != set(LIMITS):
            raise ValueError("stage_b.prior_status_invalid")
        rows.append(dict(runId=result["runId"], hashes=history.HASHES, calls=result["totals"]))
    for key, maximum in TOTAL_LIMITS.items():
        counts = [row["calls"][key] for row in rows]
        if any(type(c) is not int or c < 0 for c in counts) or sum(counts) + LIMITS[key] > maximum:
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


@contextmanager
def input_bindings():
    with patch.multiple(legacy, RUN_ID=RUN_ID, CASES=CASES, LIMITS=LIMITS):
        yield


def current_manifest(root):
    # Recreate the whole asset set, so deletion of a manifest entry cannot bypass a hash check.
    with input_bindings(), tempfile.TemporaryDirectory(prefix="codex-stage-b-v8-freeze-") as temporary:
        value = v2._prepare(Path(temporary))
    prefixes = ("config-service/src/main/resources/config/", "common-security/src/main/",
                "auth-service/src/main/", "agent-runtime/tests/system_e2e/test_knowledge_stage_b_")
    for name in legacy.git("ls-files").splitlines():
        if name.startswith(prefixes):
            value["assets"][name] = legacy.digest((legacy.REPO / name).read_bytes())
    value.update(schemaVersion=8, authorizationReference=REFERENCE,
        taskVersions=dict(selection=TASKS["action_selection"], rewrite="7", summary="6"),
        promptHashes=prompt_hashes(), maxOutputTokens=TOKENS, priorRuns=prior_bindings(),
        cumulativeLimits=TOTAL_LIMITS, runRoot=str(root.resolve()),
        qualityVersion=KNOWLEDGE_QUALITY_VERSION_V3, citationCheckVersion=CHECK_VERSION,
        datasetSha256=legacy.digest(json.dumps(dict(cases=CASES, gold=GOLD), sort_keys=True).encode()))
    return value


def prepare(root):
    if root.exists() and any(root.iterdir()):
        raise ValueError("stage_b.run_root_not_empty")
    value = current_manifest(root)
    root.mkdir(parents=True, exist_ok=True)
    legacy.write_exclusive(root / "manifest.json", value)
    return value


def validate_manifest(root, expected_sha=None):
    if any(p.name not in {"manifest.json", "authorization.json", "environment.jsonl"} or not p.is_file()
           for p in root.iterdir()):
        raise ValueError("stage_b.retry_resume_forbidden")
    raw = (root / "manifest.json").read_bytes()
    sha = legacy.digest(raw)
    if expected_sha is not None and sha != expected_sha:
        raise ValueError("stage_b.manifest_sha_mismatch")
    value = strict_json(raw)
    if not same_json(value, current_manifest(root)):
        raise ValueError("stage_b.run_08_binding_invalid")
    return value, sha


def authorization(manifest, sha):
    return dict(schemaVersion=1, runId=RUN_ID, frozenHead=manifest["frozenHead"], manifestSha256=sha,
        authorizationReference=REFERENCE, datasetSha256=manifest["datasetSha256"],
        limits=LIMITS, cumulativeLimits=TOTAL_LIMITS, live=True)


def validate_authorized(root, expected_sha):
    value, sha = validate_manifest(root, expected_sha)
    actual = strict_json((root / "authorization.json").read_bytes())
    if not same_json(actual, authorization(value, sha)):
        raise ValueError("stage_b.authorization_invalid")
    environment = [strict_json(line) for line in (root / "environment.jsonl").read_bytes().splitlines()]
    required = (
        dict(stage="local_model_readiness", embedding=True, rerank=True, model=0),
        dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0),
        dict(stage="runtime_cleanup", clientsClosed=True),
        dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True),
    )
    if any(row.get("stage") == "failure" for row in environment) or not all(
        sum(same_json(row, expected) for row in environment) == 1 for expected in required
    ):
        raise ValueError("stage_b.environment_preflight_invalid")
    return value, sha


class Run08Budget(_budget):
    def begin(self, case_spec):
        index = self.totals["e2e"]
        if index >= len(CASES) or not same_json(case_spec, CASES[index]):
            self.stopped = True
            raise ValueError("stage_b.case_order_invalid")
        super().begin(case_spec)
        self.per_case["e2e"] = 1
        self.bundle = self.summary_input = None

    def count(self, kind):
        if self.current is None or self.stopped or kind not in PER_CASE:
            self.stopped = True
            raise ValueError("stage_b.unexpected_outbound")
        if self.totals[kind] >= LIMITS[kind] or self.per_case[kind] >= PER_CASE[kind]:
            self.stopped = True
            raise ValueError("stage_b.budget_exceeded")
        self.totals[kind] += 1
        self.per_case[kind] += 1

    async def model_request(self, request):
        try:
            if self.current is None or len(self.seen_tasks) >= 3 or request.method != "POST" or str(request.url) != legacy.ModelSettings.BASE_URL + "/chat/completions":
                raise ValueError("endpoint")
            body = strict_json(request.content)
            task = tuple(TASKS)[len(self.seen_tasks)]
            messages = body["messages"]
            if (len(messages) != 2 or messages[0]["role"] != "system" or messages[1]["role"] != "user"
                or legacy.digest(messages[0]["content"].encode()) != prompt_hashes()[task]
                or type(body["max_tokens"]) is not int or body["max_tokens"] != TOKENS[task]
                or body.get("tools") or body.get("tool_choice") not in (None, "none")
                or body.get("response_format") != {"type": "json_object"}):
                raise ValueError("task")
            payload = strict_json(messages[1]["content"])
            fields = {"action_selection": {"question", "capabilities"}, "knowledge_rewrite": {"question", "domains"},
                      "knowledge_summary": {"schema_version", "question", "coverage", "evidence", "requirements"}}
            if set(payload) != fields[task] or payload["question"] != self.current["question"]:
                raise ValueError("input")
            if task == "knowledge_summary":
                if self.current["reason"] or self.bundle is None or self.summary_input is None or not same_json(
                    payload, strict_json(summary.requirement_summary_input_json(self.summary_input))):
                    raise ValueError("summary_binding")
                self.summary_evidence = [{"sha256": legacy.digest(e["content"].encode()), "content": e["content"]}
                                         for e in payload["evidence"]]
            self.count("model")
            self.seen_tasks.add(task)
            if self.totals["model"] == 1:
                legacy.write_exclusive(self.root / "consumed.json", dict(runId=RUN_ID, manifestSha256=self.manifest_sha,
                    rule="first_model_http_attempt; no retry/resume"))
            self.journal.write(json.dumps(dict(caseId=self.current["caseId"], task=task, ordinal=self.totals["model"])) + "\n")
            self.journal.flush()
            os.fsync(self.journal.fileno())
        except (KeyError, IndexError, TypeError, ValueError, OSError):
            self.stopped = True
            raise ValueError("stage_b.model_request_rejected") from None


def assess(case_spec, response, observation, budget):
    result = response.get("result") or {}
    points = result.get("points", [])
    plans = [p["plan"] for p in observation.plans if p["type"] == "knowledge_retrieval_plan"]
    domains = plans[0].get("selected_domain_ids", []) if len(plans) == 1 else []
    expected = list(TASKS.items())[:2 if case_spec["reason"] else 3]
    valid_tasks = [(r["taskId"], r["taskVersion"]) for r in observation.model_calls] == expected and all(
        r["status"] == "succeeded" for r in observation.model_calls)
    binding, checks, failure = True, {}, None
    if not case_spec["reason"]:
        binding = budget.bundle is not None and budget.summary_input is not None
        if binding:
            check = check_citations(bundle=budget.bundle, summary_input=budget.summary_input, points=points,
                                   required={name: GOLD[name] for name in case_spec["requiredGold"]})
            binding, checks, failure = check.binding_valid, dict(check.required_clauses), check.failure_reason
        else:
            checks, failure = dict.fromkeys(case_spec["requiredGold"], False), "input_binding_missing"
    quality = not plans if case_spec["reason"] else len(plans) == 1 and plans[0].get("quality_version") == KNOWLEDGE_QUALITY_VERSION_V3
    zero = not case_spec["reason"] or not observation.downstream_calls
    status = response.get("status")
    reason = result.get("reason")
    passed = (status == ("no_result" if case_spec["reason"] else "success") and
        response.get("capabilityId") == "knowledge.query" and domains == case_spec["domains"] and
        (reason == case_spec["reason"] if case_spec["reason"] else bool(points)) and
        valid_tasks and quality and zero and binding and all(checks.values()))
    # Never emit arbitrary response values or original model/data payloads.
    statuses = {"success", "no_result", "unsupported", "downstream_failure", "forbidden", "invalid_request"}
    reasons = {None, "clarification_required", "no_retrieval_hit", "insufficient_evidence", "no_matching_domain"}
    failures = [{k: r[k] for k in ("taskId", "taskVersion", "status", "failureKind")}
                for r in observation.model_calls if r["status"] != "succeeded"]
    return dict(passed=passed, status=status if status in statuses else "unexpected_status",
        reason=reason if reason in reasons else "other_reason", domains=domains, pointCount=len(points),
        requiredClauseChecks=checks, citationBindingValid=binding, citationFailure=failure,
        citationCheckVersion=CHECK_VERSION, taskBindingValid=valid_tasks, qualityBindingValid=quality,
        zeroRetrievalValid=zero, modelFailures=failures)


async def run_server(token, emit, budget=None):
    if budget is None:
        return await _run_server(token, emit, None)
    original_select = DeterministicEvidenceSelector.select
    original_build = summary._build_request

    def select(selector, **kwargs):
        value = original_select(selector, **kwargs)
        budget.bundle = value.bundle
        return value

    def build(value):
        request = original_build(value)
        budget.summary_input = value
        return request

    with (patch.object(DeterministicEvidenceSelector, "select", select),
          patch.object(summary, "_build_request", build),
          patch.object(legacy, "assess", lambda spec, response, observation, unused: assess(spec, response, observation, budget))):
        return await _run_server(token, emit, budget)


@contextmanager
def checked_services(emit, *, include_agent=False):
    # Readiness only, before the runtime factory can read model credentials.
    with legacy.httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
        for port in (8908, 8909):
            response = client.get(f"http://127.0.0.1:{port}/health")
            if response.status_code != 200:
                raise ValueError("stage_b.local_model_not_ready")
        emit(dict(stage="local_model_readiness", embedding=True, rerank=True, model=0))
    with _services(emit, include_agent=include_agent) as value:
        yield value


@contextmanager
def run_08_bindings():
    with input_bindings(), patch.multiple(legacy, Budget=Run08Budget, prepare=prepare,
            validate_manifest=validate_authorized, run_server=run_server, local_services=checked_services):
        yield


def main():
    # The old launcher owns services, cleanup and finite append-only result layout.
    if len(sys.argv) > 1 and sys.argv[1] in {"authorize", "check-environment"}:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("mode")
        parser.add_argument("--root", type=Path, required=True)
        parser.add_argument("--manifest-sha256", required=True)
        args = parser.parse_args()
        value, sha = validate_manifest(args.root, args.manifest_sha256)
        if args.mode == "authorize":
            legacy.write_exclusive(args.root / "authorization.json", authorization(value, sha))
            print(json.dumps(dict(runId=RUN_ID, manifestSha256=sha, authorized=True)))
            return
    with run_08_bindings():
        legacy.main()


if __name__ == "__main__":
    main()
