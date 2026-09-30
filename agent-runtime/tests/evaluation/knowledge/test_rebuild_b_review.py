"""Offline fake-only tests; no ES, Java, BGE, or model requests."""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

import pytest

from tests.evaluation.knowledge import rebuild_b_review as review
from tests.evaluation.knowledge import rebuild_b_reuse_binding as reuse
from tests.evaluation.knowledge.rebuild_b_comparator import (
    ArmTrace, CallTotals, CandidateRef, CaseTrace, ComparisonRun, StageRanks,
    blind_label_pool, comparison_spec_fingerprint,
)
from tests.evaluation.knowledge.rebuild_b_local_runner import _expected_profile_config_sha256
from tests.evaluation.knowledge.test_rebuild_b_reuse_binding import _scan_artifacts


def _put(path: Path, value: object) -> None:
    path.write_bytes(review._canonical_bytes(value))


@lru_cache(maxsize=1)
def _old() -> reuse.OldBuild:
    return reuse.load_old_build()


def _fake_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(review, "EVIDENCE_ROOT", tmp_path)
    old = _old()
    monkeypatch.setattr(reuse, "load_old_build", lambda **_kwargs: old)
    # The test uses the checked-in source/fixture but only synthetic scan and
    # comparison evidence. It never contacts an index or produces a real label.
    from subprocess import check_output
    frozen_head = check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    prior = json.loads(old.spec.intent_raw)["profileParameters"]
    params = {domain: {**item, "configSha256": _expected_profile_config_sha256(frozen_head, domain)}
              for domain, item in prior.items()}
    directory = tmp_path / "knowledge-b-reuse-fake-review-01"
    directory.mkdir()
    intent_raw = reuse.freeze_new_reuse_input(old=old, run_id=directory.name,
        frozen_head=frozen_head, profile_parameters=params,
        config_raw=reuse.git_blob(frozen_head, reuse.CONFIG_PATH),
        fixture_raw=reuse.git_blob(frozen_head, reuse.FIXTURE_PATH))
    sidecars, _, _ = _scan_artifacts(old, intent_raw)
    for key, name in review._SIDE_FILES.items():
        (directory / name).write_bytes(sidecars[key])
    for arm in ("source", "candidate"):
        (directory / f"{arm}-id-mapping.json").write_bytes(
            dict(old.blobs)[f"{arm}-id-mapping.json"])
    spec = reuse.spec_for_reuse(old, intent_raw=intent_raw, final_raw=sidecars["reuseFinal"])
    traces: list[CaseTrace] = []
    for case in spec.cases:
        final = case.necessary_sources
        stages = tuple(StageRanks(domain, "vector", final) for domain in case.plan.selected_domain_ids)
        keyword = tuple(StageRanks(domain, "keyword", final) for domain in case.plan.selected_domain_ids)
        rank = tuple((domain, ("id-1",)) for domain in case.plan.selected_domain_ids)
        policies = tuple((domain, "policy") for domain in case.plan.selected_domain_ids)
        baseline = ArmTrace("baseline", keyword, rank, stages, final, stages, final, policies, 1.0)
        candidate = ArmTrace("candidate", keyword, rank, stages, final, stages, final, policies, 1.0)
        traces.append(CaseTrace(case.case_id, baseline, candidate))
    run = ComparisonRun(tuple(traces), CallTotals(44, 10, 22), spec.assessment_sha256,
        spec.uat_fixture_sha256, "a" * 64, comparison_spec_fingerprint(spec), "local_verified")
    aliases = [f"b-{directory.name}-{'a' * 16}-read",
               f"b-{directory.name}-{'b' * 16}-read"]
    _put(directory / "comparison-attempt.json", {"schemaVersion": 1, "status": "consumed",
        "runId": directory.name, "frozenHead": frozen_head,
        "assessmentSha256": spec.assessment_sha256, "javaArtifactSha256": "c" * 64,
        "aliases": aliases, "budget": {"typedSearch": 44, "queryEmbedding": 10,
            "rerank": 22, "metadataEsHttp": 30, "aliasWrites": 4,
            "paid": 0, "retry": 0, "resume": 0}})
    _put(directory / "comparison-java-attestation.json", {"runId": directory.name,
        "frozenHead": frozen_head, "artifactSha256": "c" * 64,
        "buildExitCode": 0, "workingTreeTrackedClean": True})
    old_model = json.loads(dict(old.blobs)["binding.json"])["spec"]["model_snapshot"]
    model = {"schemaVersion": 1, "embedding": old_model,
             "rerank": {"container": {"id": "d" * 64}}}
    model["sha256"] = sha256(review._canonical_bytes({
        "embedding": model["embedding"], "rerank": model["rerank"]})).hexdigest()
    witness: dict[str, list[dict[str, object]]] = {}
    for arm, alias, corpus in zip(("baseline", "candidate"), aliases,
                                  (spec.source_corpus, spec.candidate_corpus), strict=True):
        witness[arm] = ([{"method": "GET", "path": f"/_alias/{alias}",
                          "request_sha256": "e" * 64, "status": 200} for _ in range(6)]
                        + [{"method": "POST", "path": f"/{corpus.index_name}/_search",
                            "request_sha256": "f" * 64, "status": 200} for _ in range(22)])
    _put(directory / "comparison-result.json", {"schemaVersion": 1,
        "runId": directory.name, "frozenHead": frozen_head,
        "status": "completed_awaiting_blind_labels", "evidenceKind": "local_verified",
        "assessmentSha256": spec.assessment_sha256,
        "uatFixtureSha256": spec.uat_fixture_sha256, "provenanceSha256": "a" * 64,
        "comparisonSpecSha256": comparison_spec_fingerprint(spec),
        "calls": asdict(run.calls), "aliasWrites": 4, "metadataEsHttp": 30,
        "ownedPids": [101, 102], "ownedProcessesStopped": True,
        "aliasesRemoved": True, "proxyViolations": 0, "paid": 0, "retry": 0,
        "resume": 0, "witness": witness, "traces": asdict(run)["cases"],
        "modelIdentityPre": model, "modelIdentityPost": model})
    _put(directory / "comparison-blind-label-pool.json", {"schemaVersion": 1,
        "runId": directory.name, "armHidden": True,
        "items": [list(key) for key in blind_label_pool(run)]})
    return directory


def _label_payload(directory: Path, template: dict[str, object]) -> bytes:
    value = dict(template)
    value["reviewerId"] = "maintainer-01"
    value["confirmation"] = review._REVIEW_CONFIRMATION
    value["items"] = [{**item, "directlyRelevant": True} for item in value["items"]]
    return review._canonical_bytes(value)


def test_completed_reuse_result_yields_unlabeled_template_and_offline_score(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = _fake_run(tmp_path, monkeypatch)
    template = review.review(directory, labels_raw=None)
    assert template["runId"] == directory.name
    assert all(item["directlyRelevant"] is None for item in template["items"])
    score = review.review(directory, labels_raw=_label_payload(directory, template))
    assert score["outcome"] == "failed"  # Equal recall is not improvement.
    assert score["unjudgedCount"] == 0
    assert score["reviewerSelfAttested"] is True
    assert score["humanIdentityIndependentlyVerified"] is False
    assert score["runtimeProvenanceIndependentlyReconstructed"] is False


def test_missing_label_stays_not_assessed(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    directory = _fake_run(tmp_path, monkeypatch)
    template = review.review(directory, labels_raw=None)
    value = json.loads(_label_payload(directory, template))
    value["items"].pop()
    score = review.review(directory, labels_raw=review._canonical_bytes(value))
    assert score["outcome"] == "not_assessed"
    assert score["unjudgedCount"] == 1
    assert score["macroBaselinePrecision"] is None


@pytest.mark.parametrize("drift", ["failed", "pool", "calls", "cleanup", "model",
                                  "witness", "head", "law_stage", "label_null",
                                  "label_foreign", "label_duplicate"])
def test_forged_or_incomplete_review_input_rejected(tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch, drift: str) -> None:
    directory = _fake_run(tmp_path, monkeypatch)
    template = review.review(directory, labels_raw=None)
    labels = json.loads(_label_payload(directory, template))
    if drift.startswith("label_"):
        if drift == "label_null":
            labels["items"][0]["directlyRelevant"] = None
        elif drift == "label_foreign":
            labels["items"][0]["caseId"] = "foreign"
        else:
            labels["items"].append(dict(labels["items"][0]))
        with pytest.raises(review.ReviewError):
            review.review(directory, labels_raw=review._canonical_bytes(labels))
        return
    if drift == "head":
        for filename in ("comparison-attempt.json", "comparison-result.json",
                         "comparison-java-attestation.json"):
            path = directory / filename
            value = json.loads(path.read_bytes())
            value["frozenHead"] = "0" * 40
            _put(path, value)
        with pytest.raises(review.ReviewError):
            review.review(directory, labels_raw=None)
        return
    filename = "comparison-blind-label-pool.json" if drift == "pool" else "comparison-result.json"
    path = directory / filename
    value = json.loads(path.read_bytes())
    if drift == "failed":
        value["status"] = "not_assessed"
    elif drift == "pool":
        value["items"].pop()
    elif drift == "calls":
        value["calls"]["typed_search"] = 0
    elif drift == "cleanup":
        value["aliasesRemoved"] = False
    elif drift == "model":
        value["modelIdentityPost"] = None
    elif drift == "law_stage":
        law_case = next(item for item in value["traces"] if item["case_id"] == "UAT-KM-006")
        law_case["baseline"]["reranked"] = []
    else:
        value["witness"]["baseline"][0]["path"] = "/foreign/_search"
    _put(path, value)
    if drift == "law_stage":
        # This forged trace keeps nonempty law retrieval but removes its
        # rerank stage; it must fail finitely during scoring, not traceback.
        fresh_template = review.review(directory, labels_raw=None)
        with pytest.raises(review.ReviewError):
            review.review(directory, labels_raw=_label_payload(directory, fresh_template))
        return
    with pytest.raises(review.ReviewError):
        review.review(directory, labels_raw=None)
