from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from knowledge_corpus_tools.b_candidate_freeze_v1 import (
    BFreezeError, GitState, _git_fixture_blob, _git_source_build_blob,
    _load_binding, _verify_source_build_evidence, execute_b_candidate_v1,
    finalize_b_assessment_v2, freeze_b_candidate_v1,
    prepare_b_mapping_scans_v1, scan_b_mapping_arm_v1,
)
from knowledge_corpus_tools.rechunk_candidate_v1 import CandidateSpec
from knowledge_corpus_tools.retrieval_representation_v2 import build_retrieval_representation_v2
from knowledge_corpus_tools.vector_candidate import canonical_bytes
from test_rechunk_candidate_v1 import FakeES, REP_TARGET, inputs, prepared

HEAD = "a" * 40
GIT = GitState("codex_0915", HEAD, True)
ORIGINAL_FIXTURE = (Path(__file__).resolve().parents[2] / "agent-runtime" / "tests" /
                    "uat" / "knowledge_rebuild_measure.v1.json").read_bytes()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def snapshot(profile_id: str, index: str, uuid: str, mapping: str) -> str:
    return sha("\n".join((profile_id, index, uuid,
                          "tax-knowledge-search-v1", mapping)).encode())


def test_git_blob_reader_returns_committed_fixture_bytes() -> None:
    root = Path(__file__).resolve().parents[2]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          capture_output=True, check=True).stdout.decode().strip()
    assert _git_fixture_blob(head) == ORIGINAL_FIXTURE
    with pytest.raises(BFreezeError, match="git_state_invalid"):
        _git_fixture_blob("not-a-commit")


def test_old_vector_source_is_bound_to_frozen_historical_build() -> None:
    root = Path(__file__).resolve().parents[2]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          capture_output=True, check=True).stdout.decode().strip()
    directory = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2"
    binding_path = f"{directory}/binding.json"
    result_path = f"{directory}/result.json"
    binding_raw = _git_source_build_blob(head, binding_path)
    result_raw = _git_source_build_blob(head, result_path)
    old_result = json.loads(result_raw)["result"]
    old_binding = json.loads(binding_raw)
    intent = {
        "sourceBuildEvidence": {
            "bindingPath": binding_path, "bindingSha256": sha(binding_raw),
            "resultPath": result_path, "resultSha256": sha(result_raw),
        },
        "source": {
            "indexName": old_result["candidate_index"],
            "indexUuid": old_result["candidate_uuid"],
            "sourceFingerprint": old_result["candidate_fingerprint"],
            "recordCount": old_result["total_count"],
        },
        "modelBindings": {
            "baselineModelSnapshotSha256": old_result["model_snapshot_sha256"],
            "baselineRepresentationVersion": old_result["representation_version"],
        },
    }
    assert sha(canonical_bytes(old_binding["modelSnapshot"])) == \
        old_result["model_snapshot_sha256"]
    _verify_source_build_evidence(intent, head)
    intent["sourceBuildEvidence"]["bindingSha256"] = "f" * 64
    with pytest.raises(BFreezeError, match="binding_invalid"):
        _verify_source_build_evidence(intent, head)


def test_local_candidate_rejects_unproven_old_model_before_attempt(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, assessment, fixture, mapping, directory)
    with pytest.raises(BFreezeError, match="binding_invalid"):
        execute_b_candidate_v1(
            directory, assessment, fixture, mapping, git_state=GIT,
            client_factory=lambda _: es.client(), preparation_factory=lambda _: prepared,
            observed_counts=lambda: (0, 0), execution_kind="local",
            fixture_blob_reader=lambda _: fixture,
            source_build_blob_reader=lambda _head, _path: b"untrusted",
        )
    assert not (directory / "attempt.json").exists() and not es.calls


def setup(tmp_path: Path) -> tuple[FakeES, bytes, bytes, bytes, bytes, Path]:
    es, _, _ = inputs(tmp_path)
    es.target_name = REP_TARGET
    content = es.source["old-1"]["content"]
    representation = build_retrieval_representation_v2(body=content, kind="body-only-v2")
    binding_sha = sha(canonical_bytes([["old-1", representation.version,
                                        representation.input_sha256,
                                        representation.body_sha256]]))
    template = es.spec(tmp_path, mode="representation", representation_binding=binding_sha)
    candidate = {key: getattr(template, key) for key in (
        "source_index", "source_uuid", "source_mapping_sha256", "source_fingerprint",
        "source_count", "read_alias", "online_index", "online_uuid",
        "online_mapping_sha256", "alias_snapshot_sha256", "candidate_index",
        "target_mapping_version", "target_mapping_sha256", "tokenizer_sha256",
        "baseline_representation_version",
    )}
    candidate["baseline_model_snapshot"] = json.loads(template.baseline_model_snapshot)
    candidate["model_snapshot"] = json.loads(template.model_snapshot)
    source = es.source["old-1"]
    row = {
        "identifier": "old-1", "document_id": source["documentId"],
        "parent_document_id": source["parentDocumentId"],
        "asset_id": source["assetId"], "asset_version": source["assetVersion"],
        "version": representation.version,
        "input_sha256": representation.input_sha256,
        "body_sha256": representation.body_sha256,
    }
    uat = json.loads(ORIGINAL_FIXTURE)
    uat["sourceCorpus"].update({
        "readAlias": template.read_alias, "index": template.source_index,
        "indexUuid": template.source_uuid, "recordCount": template.source_count,
        "mappingSha256": template.source_mapping_sha256,
        "fullFingerprint": template.source_fingerprint,
    })
    fixture = canonical_bytes(uat)
    source_by_id = {source["id"]: source for source in uat["sources"]}
    cases = []
    for original in uat["cases"]:
        if not original["retrievalDenominator"]:
            continue
        domains = original["expectedDomains"]
        settings = {"enabledDomainIds": ["tax.policy", "tax.law"],
                    "perPathCandidateLimit": 20, "finalCandidateLimit": 20,
                    "minPartialCandidates": 3, "retrievalTimeoutSeconds": 20.0,
                    "configVersion": "knowledge-minimal-v1"}
        plan = {"schemaVersion": 3, "catalogVersion": "tax-domain-catalog-v2",
                "originalQuestion": original["question"],
                "queryMode": original["queryMode"],
                "selectedDomainIds": domains,
                "profileBindings": [[domain, {"tax.policy": "tax-policy-v1",
                                               "tax.law": "tax-law-v1"}[domain]]
                                    for domain in domains],
                "settings": settings,
                "items": [
                    {"logicalDomainId": domain, "path": path,
                     "queryText": original["question"], "candidateLimit": 20,
                     "ordinal": index * 2 + offset}
                    for index, domain in enumerate(domains)
                    for offset, path in enumerate(("keyword", "vector"), start=1)
                ]}
        cases.append({
            "caseId": original["caseId"], "queryMode": original["queryMode"],
            "question": original["question"],
            "selectedDomainIds": original["expectedDomains"],
            "core": original["caseId"] in uat["thresholds"]["uat"]["coreCases"],
            "retained": True, "plan": plan, "planHash": sha(canonical_bytes(plan)),
            "necessarySources": [
                {"documentId": source_by_id[source_id]["documentId"],
                 "chunkId": source_by_id[source_id]["chunkId"],
                 "contentSha256": source_by_id[source_id]["contentSha256"]}
                for source_id in original["necessarySources"]],
        })
    budget = {"esHttp": 49, "embeddingHttp": 1, "writeOps": 1,
              "paid": 0, "retry": 0, "resume": 0,
              "onlineAliasWrites": 0, "candidates": 1}
    scan_budget = {"sourceEsHttp": 2, "candidateEsHttp": 2,
                   "retry": 0, "resume": 0}
    intent = canonical_bytes({
        "schemaVersion": 2, "kind": "knowledge_b_assessment_intent_v2",
        "uatFixtureSha256": sha(fixture),
        "source": {"indexName": template.source_index,
                   "indexUuid": template.source_uuid,
                   "mappingSha256": template.source_mapping_sha256,
                   "sourceFingerprint": template.source_fingerprint,
                   "recordCount": template.source_count},
        "candidate": {"indexName": template.candidate_index,
                      "mappingSha256": template.target_mapping_sha256,
                      "mappingVersion": template.target_mapping_version},
        "profileParameters": {
            domain: {"profileId": profile_id,
                     "profileVersion": "tax-knowledge-search-v1",
                     "readPolicyVersion": "tax-public-authenticated-v1",
                     "baselineMappingVersion": "old-mapping",
                     "candidateMappingVersion": template.target_mapping_version,
                     "configSha256": "c" * 64}
            for domain, profile_id in (("tax.policy", "tax-policy-v1"),
                                       ("tax.law", "tax-law-v1"))
        },
        "baselineProfileSnapshots": {
            domain: snapshot(profile_id, template.source_index,
                             template.source_uuid, "old-mapping")
            for domain, profile_id in (("tax.policy", "tax-policy-v1"),
                                       ("tax.law", "tax-law-v1"))
        },
        "builderBudget": budget, "mappingScanBudget": scan_budget,
        "comparisonBudget": {"typedSearch": 44, "queryEmbedding": 10,
                             "rerank": 22, "aliasWrites": 4,
                             "metadataEsHttp": 20,
                             "paid": 0, "retry": 0, "resume": 0},
        "modelBindings": {
            "baselineModelSnapshotSha256": template.baseline_model_snapshot_sha256,
            "currentModelSnapshotSha256": template.model_snapshot_sha256,
            "tokenizerSha256": template.tokenizer_sha256,
            "baselineRepresentationVersion": template.baseline_representation_version,
            "candidateRepresentationVersion": "body-only-v2",
        },
        "sourceBuildEvidence": {
            "bindingPath": "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json",
            "bindingSha256": "a" * 64,
            "resultPath": "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/result.json",
            "resultSha256": "b" * 64,
        },
        "representationBindings": [row],
        "thresholds": {
            "macroRecallStrictlyImproves": True, "macroPrecisionNoRegression": True,
            "medianLatencyRatioMax": 1.1, "coreAndRetainedNoRegression": True,
            "missingBlindLabel": "not_assessed", "unexplainedKeywordDrift": "not_assessed",
        }, "cases": cases,
    })
    mapping = canonical_bytes({
        "schemaVersion": 1, "indexName": template.source_index,
        "indexUuid": template.source_uuid,
        "sourceFingerprint": template.source_fingerprint,
        "recordCount": len(es.source),
        "records": [
            {"id": identifier, "documentId": value["documentId"],
             "chunkId": value["chunkId"], "contentSha256": sha(value["content"].encode())}
            for identifier, value in sorted(es.source.items())
        ],
    })
    request = canonical_bytes({
        "schemaVersion": 2, "runId": "knowledge-b-fake-v1", "frozenHead": HEAD,
        "assessmentIntentSha256": sha(intent), "idMappingSha256": sha(mapping),
        "candidate": candidate, "representationBindings": [row],
        "budget": budget, "mappingScanBudget": scan_budget,
    })
    return es, request, intent, fixture, mapping, tmp_path / "knowledge-b-fake-v1"


def freeze(es: FakeES, request: bytes, assessment: bytes, fixture: bytes,
           mapping: bytes, directory: Path) -> CandidateSpec:
    prepare_scan(es, request, assessment, fixture, directory)
    result = freeze_b_candidate_v1(request, assessment, fixture, mapping,
                                   directory, git_state=GIT,
                                   fixture_blob_reader=lambda _: fixture)
    assert result["status"] == "frozen_not_executed"
    assert result["sourceVerification"] == "pending_builder_live_preflight"
    binding, spec, digest = _load_binding(directory, assessment, fixture, mapping)
    assert result["bindingSha256"] == digest
    assert binding["budget"] == {"esHttp": 49, "embeddingHttp": 1,
                                  "writeOps": 1, "paid": 0, "retry": 0,
                                  "resume": 0, "onlineAliasWrites": 0, "candidates": 1}
    es.owner_alias = spec.owner_alias
    return spec


def prepare_scan(es: FakeES, request: bytes, assessment: bytes, fixture: bytes,
                 directory: Path) -> None:
    preliminary = json.loads(request)
    preliminary.pop("idMappingSha256")
    result = prepare_b_mapping_scans_v1(
        canonical_bytes(preliminary), assessment, fixture, directory,
        git_state=GIT, fixture_blob_reader=lambda _: fixture)
    assert result["status"] == "scan_plan_frozen_no_calls"
    with es.client() as client:
        scanned = scan_b_mapping_arm_v1(
            directory, arm="source", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls),
            fixture_blob_reader=lambda _: fixture)
    assert scanned["status"] == "scanned_read_only"
    es.calls.clear()


def execute(es: FakeES, assessment: bytes, fixture: bytes, mapping: bytes,
            directory: Path) -> dict[str, Any]:
    calls = [0]

    def fake_prepare(_: CandidateSpec) -> Any:
        def one_batch(items: Any) -> Any:
            calls[0] += 1
            return prepared(items)
        return one_batch

    return execute_b_candidate_v1(
        directory, assessment, fixture, mapping, git_state=GIT,
        client_factory=lambda _: es.client(), preparation_factory=fake_prepare,
        observed_counts=lambda: (len(es.calls), calls[0]), execution_kind="fake",
        fixture_blob_reader=lambda _: fixture,
    )


def test_freeze_and_one_shot_fake_build(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    spec = freeze(es, request, assessment, fixture, mapping, directory)
    assert spec.owner_alias.startswith("agent-knowledge-build-owner-")
    assert spec.representation_binding_sha256 is not None
    assert spec.assessment_intent_sha256 == sha(assessment)
    assert not es.calls
    result = execute(es, assessment, fixture, mapping, directory)
    assert result["status"] == "built_read_only_unpublished"
    assert result["updatedCount"] == 1
    assert result["paid"] == result["retry"] == result["resume"] == 0
    assert result["esHttp"] == len(es.calls) <= 49
    assert result["embeddingHttp"] == 1
    assert es.candidate_def is not None and es.candidate_def["aliases"] == {}
    saved = json.loads((directory / "result.json").read_bytes())
    assert saved == result and saved["executionKind"] == "fake"
    assert saved["assessmentIntentSha256"] == sha(assessment)
    assert saved["candidateMapping"] == "pending_postbuild_readonly_scan"
    before = len(es.calls)
    with pytest.raises(BFreezeError, match="already_consumed"):
        execute(es, assessment, fixture, mapping, directory)
    assert len(es.calls) == before
    before_scan = len(es.calls)
    with es.client() as client:
        candidate_scan = scan_b_mapping_arm_v1(
            directory, arm="candidate", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls) - before_scan,
            fixture_blob_reader=lambda _: fixture)
    assert candidate_scan["status"] == "scanned_read_only"
    assert candidate_scan["esHttp"] == 2
    source_map = json.loads((directory / "source-id-mapping.json").read_bytes())
    candidate_map = json.loads((directory / "candidate-id-mapping.json").read_bytes())
    assert source_map["records"] == candidate_map["records"]
    assert source_map["sourceFingerprint"] != candidate_map["sourceFingerprint"]
    final_result = finalize_b_assessment_v2(
        directory, assessment, fixture, git_state=GIT,
        fixture_blob_reader=lambda _: fixture)
    final = json.loads((directory / "assessment-final.json").read_bytes())
    assert final_result["status"] == "assessment_frozen"
    assert final_result["assessmentSha256"] == sha(
        (directory / "assessment-final.json").read_bytes())
    assert final["assessmentIntentSha256"] == sha(assessment)
    assert final["candidateProfileSnapshots"]["tax.policy"] != \
        json.loads(assessment)["baselineProfileSnapshots"]["tax.policy"]
    assert final["candidateProfileSnapshots"]["tax.law"] != \
        json.loads(assessment)["baselineProfileSnapshots"]["tax.law"]
    with pytest.raises(BFreezeError, match="already_frozen"):
        finalize_b_assessment_v2(directory, assessment, fixture, git_state=GIT,
                                 fixture_blob_reader=lambda _: fixture)


def test_freeze_rejects_missing_or_drifted_exact_inputs(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    prepare_scan(es, request, assessment, fixture, directory)
    body = json.loads(request)
    for change, reason in (
        ({"budget": {**body["budget"], "esHttp": 50}}, "binding_invalid"),
        ({"idMappingSha256": "f" * 64}, "binding_invalid"),
        ({"assessmentIntentSha256": "f" * 64}, "assessment_invalid"),
    ):
        bad = canonical_bytes({**body, **change})
        with pytest.raises(BFreezeError, match=reason):
            freeze_b_candidate_v1(bad, assessment, fixture, mapping,
                                  directory, git_state=GIT,
                                  fixture_blob_reader=lambda _: fixture)
        assert not (directory / "binding.json").exists() and not es.calls
    with pytest.raises(BFreezeError, match="git_state_invalid"):
        freeze_b_candidate_v1(request, assessment, fixture, mapping, directory,
                              git_state=GitState("codex_0915", HEAD, False),
                              fixture_blob_reader=lambda _: fixture)
    assert not (directory / "binding.json").exists()


def test_id_mapping_requires_order_and_unique_typed_identity(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    prepare_scan(es, request, assessment, fixture, directory)
    obj = json.loads(mapping)
    obj["records"] = list(reversed(obj["records"]))
    raw = canonical_bytes(obj)
    edited = canonical_bytes({**json.loads(request), "idMappingSha256": sha(raw)})
    with pytest.raises(BFreezeError, match="binding_invalid"):
        freeze_b_candidate_v1(edited, assessment, fixture, raw,
                              directory, git_state=GIT,
                              fixture_blob_reader=lambda _: fixture)
    assert not (directory / "binding.json").exists()
    obj = json.loads(mapping)
    obj["records"][1]["documentId"] = obj["records"][0]["documentId"]
    obj["records"][1]["chunkId"] = obj["records"][0]["chunkId"]
    obj["records"][1]["contentSha256"] = obj["records"][0]["contentSha256"]
    raw = canonical_bytes(obj)
    edited = canonical_bytes({**json.loads(request), "idMappingSha256": sha(raw)})
    with pytest.raises(BFreezeError, match="binding_invalid"):
        freeze_b_candidate_v1(edited, assessment, fixture, raw,
                              directory, git_state=GIT,
                              fixture_blob_reader=lambda _: fixture)


def test_source_or_assessment_drift_cannot_execute(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, assessment, fixture, mapping, directory)
    with pytest.raises(BFreezeError, match="binding_invalid"):
        execute(es, canonical_bytes({"schemaVersion": 1, "changed": True}),
                fixture, mapping, directory)
    assert not (directory / "attempt.json").exists() and not es.calls
    es.source["old-1"]["content"] = "drifted source"
    result = execute(es, assessment, fixture, mapping, directory)
    assert result["status"] == "failed"
    assert result["reason"] == "source_changed"
    assert result["sealStatus"] == "not_needed"
    assert es.candidate is None
    assert (directory / "attempt.json").exists()


def test_partial_bulk_failure_is_sealed_and_never_resumed(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, assessment, fixture, mapping, directory)
    es.fault = "partial_bulk"
    result = execute(es, assessment, fixture, mapping, directory)
    assert result["status"] == "failed"
    assert result["reason"] == "bulk_failed"
    assert result["sealStatus"] == "sealed"
    assert es.candidate_def is not None
    assert es.candidate_def["settings"]["index"]["blocks"]["write"] is True
    assert (directory / "result.json").exists()
    with pytest.raises(BFreezeError, match="already_consumed"):
        execute(es, assessment, fixture, mapping, directory)


def test_binding_tamper_fails_before_consumption(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, assessment, fixture, mapping, directory)
    bound = json.loads((directory / "binding.json").read_bytes())
    bound["spec"]["source_fingerprint"] = "f" * 64
    (directory / "binding.json").write_bytes(canonical_bytes(bound))
    with pytest.raises(BFreezeError, match="binding_invalid"):
        execute(es, assessment, fixture, mapping, directory)
    assert not (directory / "attempt.json").exists() and not es.calls


def test_self_hashed_binding_and_plan_drift_fail_before_consumption(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, assessment, fixture, mapping, directory)
    binding_path = directory / "binding.json"
    binding_digest = directory / "binding.sha256"
    plan_path = directory / "scan-plan.json"
    plan_digest = directory / "scan-plan.sha256"
    original_binding = binding_path.read_bytes()
    original_plan = plan_path.read_bytes()

    for changed_binding in (
        {**json.loads(original_binding), "freezeInputSha256": "f" * 64},
        {**json.loads(original_binding), "spec": {
            **json.loads(original_binding)["spec"], "source_index": "other-source"}},
    ):
        raw = canonical_bytes(changed_binding)
        binding_path.write_bytes(raw)
        binding_digest.write_text(sha(raw) + "\n", encoding="utf-8")
        with pytest.raises(BFreezeError, match="binding_invalid"):
            execute(es, assessment, fixture, mapping, directory)
        assert not (directory / "attempt.json").exists() and not es.calls
    binding_path.write_bytes(original_binding)
    binding_digest.write_text(sha(original_binding) + "\n", encoding="utf-8")

    for changed_plan in (
        {**json.loads(original_plan), "requestCoreSha256": "f" * 64},
        {**json.loads(original_plan), "sourceIndex": "other-source"},
    ):
        plan_raw = canonical_bytes(changed_plan)
        plan_path.write_bytes(plan_raw)
        plan_digest.write_text(sha(plan_raw) + "\n", encoding="utf-8")
        binding = {**json.loads(original_binding), "scanPlanSha256": sha(plan_raw)}
        binding_raw = canonical_bytes(binding)
        binding_path.write_bytes(binding_raw)
        binding_digest.write_text(sha(binding_raw) + "\n", encoding="utf-8")
        with pytest.raises(BFreezeError, match="binding_invalid"):
            execute(es, assessment, fixture, mapping, directory)
        assert not (directory / "attempt.json").exists() and not es.calls


def test_scan_plan_rejects_incomplete_assessment_and_source_drift(tmp_path: Path) -> None:
    es, request, assessment, fixture, _, directory = setup(tmp_path)
    preliminary = json.loads(request)
    preliminary.pop("idMappingSha256")
    for changed_assessment in (
        canonical_bytes({}),
        canonical_bytes({**json.loads(assessment), "thresholds": {
            **json.loads(assessment)["thresholds"],
            "macroRecallStrictlyImproves": 1,
        }}),
        canonical_bytes({**json.loads(assessment), "cases": [
            {**json.loads(assessment)["cases"][0], "planHash": "f" * 64},
            *json.loads(assessment)["cases"][1:]]}),
    ):
        edited = {**preliminary, "assessmentIntentSha256": sha(changed_assessment)}
        with pytest.raises(BFreezeError, match="assessment_invalid"):
            prepare_b_mapping_scans_v1(canonical_bytes(edited), changed_assessment,
                                       fixture, directory, git_state=GIT,
                                       fixture_blob_reader=lambda _: fixture)
        assert not directory.exists() and not es.calls
    changed = json.loads(fixture)
    changed["sourceCorpus"]["fullFingerprint"] = "f" * 64
    changed_fixture = canonical_bytes(changed)
    changed_assessment = canonical_bytes({**json.loads(assessment),
                                          "uatFixtureSha256": sha(changed_fixture)})
    edited = {**preliminary, "assessmentIntentSha256": sha(changed_assessment)}
    with pytest.raises(BFreezeError, match="binding_invalid"):
        prepare_b_mapping_scans_v1(canonical_bytes(edited), changed_assessment,
                                   changed_fixture, directory, git_state=GIT,
                                   fixture_blob_reader=lambda _: changed_fixture)
    assert not directory.exists()


def test_candidate_mapping_drift_is_not_assessed(tmp_path: Path) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, assessment, fixture, mapping, directory)
    result = execute(es, assessment, fixture, mapping, directory)
    assert result["status"] == "built_read_only_unpublished"
    assert es.candidate is not None
    es.candidate["old-1"]["content"] = "drifted candidate body"
    before = len(es.calls)
    with es.client() as client:
        scanned = scan_b_mapping_arm_v1(
            directory, arm="candidate", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls) - before,
            fixture_blob_reader=lambda _: fixture)
    assert scanned["status"] == "failed"
    assert scanned["reason"] == "scan_fingerprint_drift"
    assert scanned["esHttp"] == 2
    assert not (directory / "candidate-id-mapping.json").exists()
    assert (directory / "candidate-mapping-scan-attempt.json").exists()
    assert (directory / "candidate-mapping-scan-result.json").exists()
    with es.client() as client, pytest.raises(BFreezeError, match="already_consumed"):
        scan_b_mapping_arm_v1(
            directory, arm="candidate", git_state=GIT, client=client,
            observed_calls=lambda: 0,
            fixture_blob_reader=lambda _: fixture)


def test_intent_rejects_old_assessment_and_preguessed_candidate_identity(
    tmp_path: Path,
) -> None:
    es, request, intent, fixture, _, directory = setup(tmp_path)
    preliminary = json.loads(request)
    preliminary.pop("idMappingSha256")
    for change in (
        {"schemaVersion": 1, "kind": "knowledge_b_retrieval_assessment_v1"},
        {"candidateUuid": "guessed-before-build"},
        {"candidateProfileSnapshots": {"tax.policy": "a" * 64,
                                       "tax.law": "b" * 64}},
    ):
        changed = canonical_bytes({**json.loads(intent), **change})
        preliminary["assessmentIntentSha256"] = sha(changed)
        with pytest.raises(BFreezeError, match="assessment_invalid"):
            prepare_b_mapping_scans_v1(
                canonical_bytes(preliminary), changed, fixture, directory,
                git_state=GIT, fixture_blob_reader=lambda _: fixture)
        assert not directory.exists() and not es.calls


def test_final_assessment_requires_verified_candidate_and_is_append_only(
    tmp_path: Path,
) -> None:
    es, request, intent, fixture, mapping, directory = setup(tmp_path)
    freeze(es, request, intent, fixture, mapping, directory)
    assert execute(es, intent, fixture, mapping, directory)["status"] == \
        "built_read_only_unpublished"
    with pytest.raises(BFreezeError, match="binding_invalid"):
        finalize_b_assessment_v2(directory, intent, fixture, git_state=GIT,
                                 fixture_blob_reader=lambda _: fixture)
    assert not (directory / "assessment-final.json").exists()
    before = len(es.calls)
    with es.client() as client:
        assert scan_b_mapping_arm_v1(
            directory, arm="candidate", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls) - before,
            fixture_blob_reader=lambda _: fixture)["status"] == "scanned_read_only"
    result_path = directory / "result.json"
    original = result_path.read_bytes()
    tampered = json.loads(original)
    tampered["candidateUuid"] = "other-uuid"
    result_path.write_bytes(canonical_bytes(tampered))
    with pytest.raises(BFreezeError, match="binding_invalid"):
        finalize_b_assessment_v2(directory, intent, fixture, git_state=GIT,
                                 fixture_blob_reader=lambda _: fixture)
    assert not (directory / "assessment-final.json").exists()
    tampered = json.loads(original)
    tampered.pop("candidateFingerprint")
    result_path.write_bytes(canonical_bytes(tampered))
    with pytest.raises(BFreezeError, match="binding_invalid"):
        finalize_b_assessment_v2(directory, intent, fixture, git_state=GIT,
                                 fixture_blob_reader=lambda _: fixture)
    assert not (directory / "assessment-final.json").exists()
    result_path.write_bytes(original)
    assert finalize_b_assessment_v2(
        directory, intent, fixture, git_state=GIT,
        fixture_blob_reader=lambda _: fixture)["status"] == "assessment_frozen"
    assert (directory / "assessment-final.sha256").read_text().strip() == sha(
        (directory / "assessment-final.json").read_bytes())


def test_frozen_head_fixture_blob_is_required_before_any_scan_or_build(
    tmp_path: Path,
) -> None:
    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    preliminary = json.loads(request)
    preliminary.pop("idMappingSha256")
    wrong_blob = fixture + b" "
    with pytest.raises(BFreezeError, match="assessment_invalid"):
        prepare_b_mapping_scans_v1(
            canonical_bytes(preliminary), assessment, fixture, directory,
            git_state=GIT, fixture_blob_reader=lambda _: wrong_blob)
    assert not directory.exists() and not es.calls

    plan = prepare_b_mapping_scans_v1(
        canonical_bytes(preliminary), assessment, fixture, directory,
        git_state=GIT, fixture_blob_reader=lambda _: fixture)
    assert plan["status"] == "scan_plan_frozen_no_calls"
    with es.client() as client, pytest.raises(BFreezeError,
                                               match="assessment_invalid"):
        scan_b_mapping_arm_v1(
            directory, arm="source", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls),
            fixture_blob_reader=lambda _: wrong_blob)
    assert not es.calls and not (directory / "source-mapping-scan-attempt.json").exists()

    with es.client() as client:
        scan_b_mapping_arm_v1(
            directory, arm="source", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls),
            fixture_blob_reader=lambda _: fixture)
    es.calls.clear()
    with pytest.raises(BFreezeError, match="assessment_invalid"):
        freeze_b_candidate_v1(
            request, assessment, fixture, mapping, directory,
            git_state=GIT, fixture_blob_reader=lambda _: wrong_blob)
    assert not (directory / "binding.json").exists() and not es.calls
    freeze_b_candidate_v1(
        request, assessment, fixture, mapping, directory,
        git_state=GIT, fixture_blob_reader=lambda _: fixture)
    with pytest.raises(BFreezeError, match="assessment_invalid"):
        execute_b_candidate_v1(
            directory, assessment, fixture, mapping, git_state=GIT,
            client_factory=lambda _: es.client(),
            preparation_factory=lambda _: prepared,
            observed_counts=lambda: (0, 0), execution_kind="fake",
            fixture_blob_reader=lambda _: wrong_blob)
    assert not (directory / "attempt.json").exists() and not es.calls


def test_comparator_accepts_real_freeze_and_two_fake_scan_sidecars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.syspath_prepend(str(root / "agent-runtime"))
    monkeypatch.syspath_prepend(str(root / "agent-runtime" / "src"))
    from agent_runtime.knowledge.intent_contracts import (
        KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput,
        KnowledgeQueryMode,
    )
    from agent_runtime.knowledge.minimal_plan import (
        MinimalKnowledgePlanBuilder, MinimalRetrievalSettings,
    )
    from tests.evaluation.knowledge.rebuild_b_comparator import (
        ArmEndpoint, ComparisonSpec, FrozenIdMapping, _verify_provenance,
    )

    es, request, assessment, fixture, mapping, directory = setup(tmp_path)
    cases = json.loads(assessment)["cases"]
    plans = {}
    for case in cases:
        domains = tuple(case["selectedDomainIds"])
        plans[case["caseId"]] = MinimalKnowledgePlanBuilder().build(
            question=KnowledgeQueryIntentInput(minimized_question=case["question"]),
            intent=KnowledgeQueryIntent(
                query_mode=KnowledgeQueryMode(case["queryMode"]),
                selected_domain_ids=domains, missing_conditions=(),
                outcome=KnowledgeIntentOutcome.SEARCH,
            ),
            settings=MinimalRetrievalSettings(),
        )
    freeze(es, request, assessment, fixture, mapping, directory)
    assert execute(es, assessment, fixture, mapping, directory)["status"] == \
        "built_read_only_unpublished"
    before = len(es.calls)
    with es.client() as client:
        scanned = scan_b_mapping_arm_v1(
            directory, arm="candidate", git_state=GIT, client=client,
            observed_calls=lambda: len(es.calls) - before,
            fixture_blob_reader=lambda _: fixture)
    assert scanned["status"] == "scanned_read_only"
    assert finalize_b_assessment_v2(
        directory, assessment, fixture, git_state=GIT,
        fixture_blob_reader=lambda _: fixture)["status"] == "assessment_frozen"
    final_raw = (directory / "assessment-final.json").read_bytes()
    frozen = ComparisonSpec.from_assessment_bytes(
        final_raw, expected_sha256=sha(final_raw),
        intent_raw=assessment, expected_intent_sha256=sha(assessment),
        uat_fixture_raw=fixture, authoritative_fixture_sha256=sha(fixture),
        plans=plans,
    )
    source_raw = (directory / "source-id-mapping.json").read_bytes()
    candidate_raw = (directory / "candidate-id-mapping.json").read_bytes()
    snapshots = dict(frozen.profile_snapshots)
    baseline = ArmEndpoint(search=None, snapshots=snapshots["baseline"],
        id_mapping=FrozenIdMapping.from_bytes(source_raw, expected_sha256=sha(source_raw)))
    candidate = ArmEndpoint(search=None, snapshots=snapshots["candidate"],
        id_mapping=FrozenIdMapping.from_bytes(candidate_raw,
                                               expected_sha256=sha(candidate_raw)))
    sidecars = {name: (directory / filename).read_bytes() for name, filename in {
        "scanPlan": "scan-plan.json", "binding": "binding.json",
        "builderResult": "result.json",
        "sourceScanResult": "source-mapping-scan-result.json",
        "candidateScanResult": "candidate-mapping-scan-result.json",
    }.items()}
    digest, execution_kind = _verify_provenance(frozen, baseline, candidate, sidecars)
    assert len(digest) == 64
    assert execution_kind == "fake"
