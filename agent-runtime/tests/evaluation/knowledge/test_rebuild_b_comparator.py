"""Synthetic-only B comparison tests; no sockets, ES, BGE or LLM are opened."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath
from agent_runtime.knowledge.intent_contracts import (
    KnowledgeIntentOutcome, KnowledgeQueryIntent, KnowledgeQueryIntentInput, KnowledgeQueryMode,
)
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgePlanBuilder, MinimalRetrievalSettings
from agent_runtime.knowledge.retrieval.contracts import PathResultKind, PathRetrievalResult, RerankScore
from tests.evaluation.knowledge.rebuild_b_comparator import (
    ArmEndpoint, CandidateRef, ComparisonCase, ComparisonRunError, ComparisonSpec, FrozenIdMapping,
    SourceCorpusBinding,
    blind_label_pool, plan_fingerprint, plan_payload, run_comparison, score_comparison,
)
from tests.helpers import ManualCancellationSignal, scope
from tests.retrieval_helpers import candidate
from tests.unit.knowledge.test_minimal_retrieval_plan import make_plan


CASE_IDS = ("UAT-KM-001", "UAT-KM-002", "UAT-KM-003", "UAT-KM-005", "UAT-KM-006",
            "UAT-KM-007", "UAT-KM-008", "UAT-KM-009", "UAT-KM-011", "UAT-KM-012")
COMMITTED_UAT_FIXTURE_SHA256 = "e673988d0898f04eaff5f108ba3b08d7edd5abb85b15f05777ca2bf9301d7630"
CANDIDATE_INPUT_KEYS = (
    "source_index", "source_uuid", "source_mapping_sha256", "source_fingerprint",
    "source_count", "read_alias", "online_index", "online_uuid",
    "online_mapping_sha256", "alias_snapshot_sha256", "candidate_index",
    "target_mapping_version", "target_mapping_sha256", "baseline_model_snapshot",
    "model_snapshot", "tokenizer_sha256", "baseline_representation_version",
)


def canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


PROFILE_PARAMETERS = {
    domain: {"profileId": profile_id, "profileVersion": "tax-knowledge-search-v1",
             "readPolicyVersion": "tax-public-authenticated-v1",
             "baselineMappingVersion": "synthetic-baseline-map-v1",
             "candidateMappingVersion": "synthetic-mapping-v1", "configSha256": "8" * 64}
    for domain, profile_id in (("tax.policy", "tax-policy-v1"),
                               ("tax.law", "tax-law-v1"))
}


def snapshots(arm: str, index_name: str | None = None,
              index_uuid: str | None = None) -> tuple[tuple[str, str], ...]:
    name = index_name or ("full-baseline" if arm == "baseline" else "full-candidate")
    uuid = index_uuid or name + "Uuid"
    version = "baselineMappingVersion" if arm == "baseline" else "candidateMappingVersion"
    return tuple((domain, hashlib.sha256("\n".join((param["profileId"], name,
        uuid, param["profileVersion"], param[version])).encode()).hexdigest())
        for domain, param in PROFILE_PARAMETERS.items())


def required(case_id: str, domain: str = "tax.policy") -> CandidateRef:
    return CandidateRef.from_candidate(candidate(chunk=f"required-{case_id}-{domain}", domain=domain))


def spec() -> ComparisonSpec:
    cases = []
    for case_id in CASE_IDS:
        domains = (("tax.law",) if case_id in ("UAT-KM-006", "UAT-KM-008", "UAT-KM-011") else
                   ("tax.policy", "tax.law") if case_id == "UAT-KM-007" else ("tax.policy",))
        cases.append(ComparisonCase(case_id=case_id,
            plan=make_plan(domains, question=f"查询公开税务资料 {case_id}"),
            necessary_sources=tuple(required(case_id, domain) for domain in domains),
            core=case_id in ("UAT-KM-001", "UAT-KM-005", "UAT-KM-009"), retained=True))
    empty = canonical({})
    base = ComparisonSpec(tuple(cases),
        (("baseline", snapshots("baseline")), ("candidate", snapshots("candidate"))),
        "d" * 64, hashlib.sha256(empty).hexdigest(), hashlib.sha256(empty).hexdigest(),
        SourceCorpusBinding("full-baseline", "full-baselineUuid", 80, "0" * 64, "1" * 64),
        SourceCorpusBinding("full-candidate", "full-candidateUuid", 80, "f" * 64, "2" * 64),
        empty, empty)
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    initial = provenance_sidecars(base, baseline, proposed)
    intent = assessment_intent_raw(base, initial)
    bound = replace(base, intent_raw=intent,
                    assessment_intent_sha256=hashlib.sha256(intent).hexdigest())
    sidecars = provenance_sidecars(bound, baseline, proposed)
    final = assessment_final_raw(bound, sidecars, baseline, proposed)
    return replace(bound, final_raw=final, assessment_sha256=hashlib.sha256(final).hexdigest())


def assessment_intent_raw(frozen: ComparisonSpec, sidecars: dict[str, bytes]) -> bytes:
    binding = json.loads(sidecars["binding"])
    source = frozen.source_corpus
    proposed = frozen.candidate_corpus
    value = {
        "schemaVersion": 2,
        "kind": "knowledge_b_assessment_intent_v2",
        "uatFixtureSha256": frozen.uat_fixture_sha256,
        "source": {"indexName": source.index_name, "indexUuid": source.index_uuid,
                   "mappingSha256": source.mapping_sha256,
                   "sourceFingerprint": source.full_fingerprint,
                   "recordCount": source.record_count},
        "candidate": {"indexName": proposed.index_name,
                      "mappingSha256": proposed.mapping_sha256,
                      "mappingVersion": "synthetic-mapping-v1"},
        "profileParameters": PROFILE_PARAMETERS,
        "baselineProfileSnapshots": dict(dict(frozen.profile_snapshots)["baseline"]),
        "builderBudget": binding["budget"],
        "mappingScanBudget": binding["mappingScanBudget"],
        "comparisonBudget": {"typedSearch": 44, "queryEmbedding": 10,
            "rerank": 22, "aliasWrites": 4, "metadataEsHttp": 20,
            "paid": 0, "retry": 0, "resume": 0},
        "representationBindings": binding["representationBindings"],
        "modelBindings": {
            "baselineModelSnapshotSha256": binding["spec"]["baseline_model_snapshot_sha256"],
            "currentModelSnapshotSha256": binding["spec"]["model_snapshot_sha256"],
            "tokenizerSha256": binding["spec"]["tokenizer_sha256"],
            "baselineRepresentationVersion": binding["spec"]["baseline_representation_version"],
            "candidateRepresentationVersion": binding["spec"]["representation_version"]},
        "sourceBuildEvidence": {
            "bindingPath": "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json",
            "bindingSha256": "a" * 64,
            "resultPath": "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/result.json",
            "resultSha256": "b" * 64,
        },
        "cases": [{
            "caseId": item.case_id,
            "question": item.plan.original_question,
            "queryMode": item.plan.query_mode.value,
            "selectedDomainIds": list(item.plan.selected_domain_ids),
            "necessarySources": [{"documentId": ref.document_id,
                                  "chunkId": ref.chunk_id,
                                  "contentSha256": ref.content_sha256}
                                 for ref in item.necessary_sources],
            "core": item.core,
            "retained": item.retained,
            "plan": plan_payload(item.plan),
            "planHash": plan_fingerprint(item.plan),
        } for item in frozen.cases],
        "thresholds": {
            "macroRecallStrictlyImproves": True,
            "macroPrecisionNoRegression": True,
            "medianLatencyRatioMax": 1.10,
            "coreAndRetainedNoRegression": True,
            "missingBlindLabel": "not_assessed",
            "unexplainedKeywordDrift": "not_assessed",
        },
    }
    return canonical(value)


def assessment_final_raw(frozen: ComparisonSpec, sidecars: dict[str, bytes],
                         baseline: ArmEndpoint, proposed: ArmEndpoint) -> bytes:
    candidate = frozen.candidate_corpus
    return canonical({
        "schemaVersion": 2, "kind": "knowledge_b_retrieval_assessment_v2",
        "assessmentIntentSha256": frozen.assessment_intent_sha256,
        "bindingSha256": hashlib.sha256(sidecars["binding"]).hexdigest(),
        "builderResultSha256": hashlib.sha256(sidecars["builderResult"]).hexdigest(),
        "sourceMapScanResultSha256": hashlib.sha256(sidecars["sourceScanResult"]).hexdigest(),
        "candidateMapScanResultSha256": hashlib.sha256(sidecars["candidateScanResult"]).hexdigest(),
        "sourceIdMappingSha256": baseline.id_mapping.sha256,
        "candidateIdMappingSha256": proposed.id_mapping.sha256,
        "candidateIdentity": {"indexName": candidate.index_name,
            "indexUuid": candidate.index_uuid, "mappingSha256": candidate.mapping_sha256,
            "sourceFingerprint": candidate.full_fingerprint, "recordCount": candidate.record_count},
        "candidateProfileSnapshots": dict(dict(frozen.profile_snapshots)["candidate"]),
    })


def rebind_final_to_intent(final_raw: bytes, intent_raw: bytes) -> bytes:
    value = json.loads(final_raw)
    value["assessmentIntentSha256"] = hashlib.sha256(intent_raw).hexdigest()
    return canonical(value)


def synthetic_uat_fixture_raw(frozen: ComparisonSpec) -> bytes:
    cases_by_id = {item.case_id: item for item in frozen.cases}
    sources = []
    cases = []
    for number in range(1, 13):
        case_id = f"UAT-KM-{number:03d}"
        item = cases_by_id.get(case_id)
        required_ids = []
        if item is not None:
            for index, ref in enumerate(item.necessary_sources):
                source_id = f"source-{number}-{index}"
                sources.append({"id": source_id, "documentId": ref.document_id,
                    "chunkId": ref.chunk_id, "contentSha256": ref.content_sha256})
                required_ids.append(source_id)
        cases.append({"caseId": case_id, "retrievalDenominator": item is not None,
            "question": item.plan.original_question if item else "无需检索",
            "queryMode": item.plan.query_mode.value if item else "lookup",
            "expectedDomains": list(item.plan.selected_domain_ids) if item else [],
            "necessarySources": required_ids})
    corpus = frozen.source_corpus
    value = {"schemaVersion": 1, "datasetId": "knowledge-rebuild-measure-v1",
        "sourceCorpus": {"index": corpus.index_name, "indexUuid": corpus.index_uuid,
            "recordCount": corpus.record_count, "mappingSha256": corpus.mapping_sha256,
            "fullFingerprint": corpus.full_fingerprint},
        "sources": sources, "cases": cases,
        "thresholds": {"uat": {"coreCases": [item.case_id for item in frozen.cases if item.core]},
            "comparisonB": {"retainedCases": list(CASE_IDS)}}}
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()


def test_assessment_exact_schema_and_real_plan_binding():
    frozen = spec()
    fixture = synthetic_uat_fixture_raw(frozen)
    frozen = replace(frozen, uat_fixture_sha256=hashlib.sha256(fixture).hexdigest())
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)
    intent_raw = assessment_intent_raw(frozen, sidecars)
    frozen = replace(frozen, intent_raw=intent_raw,
                     assessment_intent_sha256=hashlib.sha256(intent_raw).hexdigest())
    raw = assessment_final_raw(frozen, sidecars, baseline, proposed)
    plans = {case.case_id: case.plan for case in frozen.cases}
    parsed = ComparisonSpec.from_assessment_bytes(raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(), intent_raw=intent_raw,
        expected_intent_sha256=hashlib.sha256(intent_raw).hexdigest(), uat_fixture_raw=fixture,
        authoritative_fixture_sha256=hashlib.sha256(fixture).hexdigest(), plans=plans)
    assert parsed.cases == frozen.cases
    assert parsed.profile_snapshots == frozen.profile_snapshots
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(b"{}\n",
            expected_sha256=hashlib.sha256(b"{}\n").hexdigest(),
            intent_raw=intent_raw, expected_intent_sha256=hashlib.sha256(intent_raw).hexdigest(),
            uat_fixture_raw=fixture,
            authoritative_fixture_sha256=hashlib.sha256(fixture).hexdigest(), plans=plans)
    changed = json.loads(intent_raw)
    changed["cases"][0]["plan"]["items"][0]["candidateLimit"] = 19
    modified = canonical(changed)
    changed_final = rebind_final_to_intent(raw, modified)
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(changed_final,
            expected_sha256=hashlib.sha256(changed_final).hexdigest(), intent_raw=modified,
            expected_intent_sha256=hashlib.sha256(modified).hexdigest(),
            uat_fixture_raw=fixture,
            authoritative_fixture_sha256=hashlib.sha256(fixture).hexdigest(), plans=plans)


@pytest.mark.parametrize("drift", ["budget", "zero_budget", "representation", "model", "law_mapping",
                                     "source", "old_stage"])
def test_two_stage_intent_rejects_forged_prebuild_contract(drift):
    frozen = spec()
    fixture = synthetic_uat_fixture_raw(frozen)
    frozen = replace(frozen, uat_fixture_sha256=hashlib.sha256(fixture).hexdigest())
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)
    intent = json.loads(assessment_intent_raw(frozen, sidecars))
    if drift == "budget":
        intent["comparisonBudget"]["metadataEsHttp"] = 513
    elif drift == "zero_budget":
        intent["comparisonBudget"]["metadataEsHttp"] = 0
    elif drift == "representation":
        intent["representationBindings"] = []
    elif drift == "model":
        intent["modelBindings"]["candidateRepresentationVersion"] = "unbound"
    elif drift == "law_mapping":
        intent["profileParameters"]["tax.law"]["candidateMappingVersion"] = "other"
    elif drift == "source":
        intent["source"]["recordCount"] = 79
    else:
        intent["schemaVersion"] = 1
        intent["kind"] = "knowledge_b_retrieval_assessment_v1"
    changed_intent = canonical(intent)
    final = assessment_final_raw(frozen, sidecars, baseline, proposed)
    changed_final = rebind_final_to_intent(final, changed_intent)
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(changed_final,
            expected_sha256=hashlib.sha256(changed_final).hexdigest(),
            intent_raw=changed_intent,
            expected_intent_sha256=hashlib.sha256(changed_intent).hexdigest(),
            uat_fixture_raw=fixture,
            authoritative_fixture_sha256=hashlib.sha256(fixture).hexdigest(),
            plans={case.case_id: case.plan for case in frozen.cases})


def test_both_domains_candidate_snapshot_is_bound_to_candidate_physical_index():
    frozen = spec()
    assert all(dict(frozen.profile_snapshots)["baseline"][index][1]
               != dict(frozen.profile_snapshots)["candidate"][index][1]
               for index in range(2))
    assert dict(dict(frozen.profile_snapshots)["candidate"])["tax.law"] == dict(
        snapshots("candidate"))["tax.law"]
    fake_fixture = synthetic_uat_fixture_raw(frozen)
    frozen = replace(frozen, uat_fixture_sha256=hashlib.sha256(fake_fixture).hexdigest())
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)
    intent_raw = assessment_intent_raw(frozen, sidecars)
    frozen = replace(frozen, intent_raw=intent_raw,
                     assessment_intent_sha256=hashlib.sha256(intent_raw).hexdigest())
    changed = json.loads(assessment_final_raw(frozen, sidecars, baseline, proposed))
    changed["candidateProfileSnapshots"]["tax.law"] = dict(
        dict(frozen.profile_snapshots)["baseline"])["tax.law"]
    # The self-reported final SHA is insufficient to change a physical Profile binding.
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(canonical(changed),
            expected_sha256=digest(changed), intent_raw=frozen.intent_raw,
            expected_intent_sha256=frozen.assessment_intent_sha256,
            uat_fixture_raw=fake_fixture,
            authoritative_fixture_sha256=hashlib.sha256(fake_fixture).hexdigest(),
            plans={case.case_id: case.plan for case in frozen.cases})


def test_committed_twelve_case_fixture_is_the_ten_case_authority():
    fixture_raw = (Path(__file__).parents[2] / "uat" /
                   "knowledge_rebuild_measure.v1.json").read_bytes()
    assert hashlib.sha256(fixture_raw).hexdigest() == COMMITTED_UAT_FIXTURE_SHA256
    fixture = json.loads(fixture_raw)
    source_by_id = {item["id"]: item for item in fixture["sources"]}
    rows = [item for item in fixture["cases"] if item["retrievalDenominator"]]
    assert tuple(item["caseId"] for item in rows) == CASE_IDS
    cases = []
    for row in rows:
        domains = tuple(row["expectedDomains"])
        plan = MinimalKnowledgePlanBuilder().build(
            question=KnowledgeQueryIntentInput(minimized_question=row["question"]),
            intent=KnowledgeQueryIntent(query_mode=KnowledgeQueryMode(row["queryMode"]),
                selected_domain_ids=domains, missing_conditions=(),
                outcome=KnowledgeIntentOutcome.SEARCH),
            settings=MinimalRetrievalSettings())
        refs = tuple(CandidateRef(source_by_id[source_id]["documentId"],
            source_by_id[source_id]["chunkId"], source_by_id[source_id]["contentSha256"])
            for source_id in row["necessarySources"])
        cases.append(ComparisonCase(row["caseId"], plan, refs,
            row["caseId"] in fixture["thresholds"]["uat"]["coreCases"], True))
    source = fixture["sourceCorpus"]
    empty = canonical({})
    frozen = ComparisonSpec(tuple(cases),
        (("baseline", snapshots("baseline", source["index"], source["indexUuid"])),
         ("candidate", snapshots("candidate"))),
        COMMITTED_UAT_FIXTURE_SHA256, hashlib.sha256(empty).hexdigest(),
        hashlib.sha256(empty).hexdigest(),
        SourceCorpusBinding(source["index"], source["indexUuid"], source["recordCount"],
                            source["mappingSha256"], source["fullFingerprint"]),
        SourceCorpusBinding("full-candidate", "full-candidateUuid", source["recordCount"],
                            "f" * 64, "2" * 64), empty, empty)
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)
    intent_raw = assessment_intent_raw(frozen, sidecars)
    frozen = replace(frozen, intent_raw=intent_raw,
                     assessment_intent_sha256=hashlib.sha256(intent_raw).hexdigest())
    raw = assessment_final_raw(frozen, sidecars, baseline, proposed)
    plans = {case.case_id: case.plan for case in frozen.cases}
    parsed = ComparisonSpec.from_assessment_bytes(raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(), intent_raw=intent_raw,
        expected_intent_sha256=hashlib.sha256(intent_raw).hexdigest(), uat_fixture_raw=fixture_raw,
        authoritative_fixture_sha256=COMMITTED_UAT_FIXTURE_SHA256, plans=plans)
    assert parsed.cases == frozen.cases and parsed.source_corpus.record_count == 15521
    changed = json.loads(intent_raw)
    changed["cases"][0]["necessarySources"] = changed["cases"][0]["necessarySources"][:1]
    modified = canonical(changed)
    changed_final = rebind_final_to_intent(raw, modified)
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(changed_final,
            expected_sha256=hashlib.sha256(changed_final).hexdigest(), intent_raw=modified,
            expected_intent_sha256=hashlib.sha256(modified).hexdigest(), uat_fixture_raw=fixture_raw,
            authoritative_fixture_sha256=COMMITTED_UAT_FIXTURE_SHA256, plans=plans)
    fake_fixture = fixture_raw.replace("查找财税".encode(), "寻找财税".encode(), 1)
    assert fake_fixture != fixture_raw
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(), intent_raw=intent_raw,
            expected_intent_sha256=hashlib.sha256(intent_raw).hexdigest(), uat_fixture_raw=fake_fixture,
            authoritative_fixture_sha256=COMMITTED_UAT_FIXTURE_SHA256, plans=plans)
    changed = json.loads(intent_raw)
    changed["thresholds"]["medianLatencyRatioMax"] = 1.20
    modified = canonical(changed)
    changed_final = rebind_final_to_intent(raw, modified)
    with pytest.raises(ValueError, match="comparison_invalid"):
        ComparisonSpec.from_assessment_bytes(changed_final,
            expected_sha256=hashlib.sha256(changed_final).hexdigest(), intent_raw=modified,
            expected_intent_sha256=hashlib.sha256(modified).hexdigest(),
            uat_fixture_raw=fixture_raw,
            authoritative_fixture_sha256=COMMITTED_UAT_FIXTURE_SHA256, plans=plans)


class FakeSearch:
    def __init__(self, arm: str, *, keyword_drift: bool = False, denied: bool = False,
                 no_result: bool = False, events: list[tuple[str, str]] | None = None) -> None:
        self.arm = arm
        self.keyword_drift = keyword_drift
        self.denied = denied
        self.no_result = no_result
        self.events = events if events is not None else []
        self.calls: list[tuple[str, RetrievalPath]] = []
        self.contexts: list[KnowledgeRetrievalContext] = []

    async def search(self, *, request, context, timeout_s):
        case_id = context.request_id
        self.calls.append((case_id, request.path))
        self.contexts.append(context)
        self.events.append((case_id, self.arm))
        await asyncio.sleep(0)
        if self.denied:
            return PathRetrievalResult(kind=PathResultKind.FORBIDDEN, logical_domain_id=request.logical_domain_id,
                retrieval_profile_id=request.retrieval_profile_id, path=request.path)
        if self.no_result and case_id == CASE_IDS[0]:
            snapshot = dict(snapshots(self.arm))[request.logical_domain_id]
            return PathRetrievalResult(kind=PathResultKind.NO_RESULT,
                logical_domain_id=request.logical_domain_id, retrieval_profile_id=request.retrieval_profile_id,
                path=request.path, profile_version="tax-knowledge-search-v1", index_snapshot_id=snapshot,
                read_policy_version="tax-public-authenticated-v1")
        if request.path is RetrievalPath.KEYWORD:
            name = "keyword-changed" if self.keyword_drift and case_id == CASE_IDS[0] else "keyword"
        elif self.arm == "baseline" and case_id == CASE_IDS[0]:
            name = "vector-unrelated"
        else:
            name = "required"
        selected = candidate(chunk=f"{name}-{case_id}-{request.logical_domain_id}",
            domain=request.logical_domain_id)
        snapshot = dict(snapshots(self.arm))[request.logical_domain_id]
        selected = replace(selected, index_snapshot_id=snapshot)
        return PathRetrievalResult(kind=PathResultKind.CANDIDATES,
            logical_domain_id=request.logical_domain_id, retrieval_profile_id=request.retrieval_profile_id,
            path=request.path, profile_version="tax-knowledge-search-v1",
            index_snapshot_id=snapshot, read_policy_version="tax-public-authenticated-v1",
            candidates=(selected,))


class FakeEmbedding:
    def __init__(self, *, invalid: bool = False) -> None:
        self.calls: list[str] = []
        self.invalid = invalid

    async def embed(self, *, text, timeout_s):
        self.calls.append(text)
        return (0.0,) * (1023 if self.invalid else 1024)


class FakeRerank:
    def __init__(self) -> None:
        self.calls = 0

    async def rerank(self, *, query, candidates, timeout_s):
        self.calls += 1
        return tuple(RerankScore(candidate_index=i, score=float(len(candidates) - i))
                     for i in range(len(candidates)))


class TickClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 0.01
        return self.value


def context_for(case_id: str) -> KnowledgeRetrievalContext:
    return KnowledgeRetrievalContext(request_id=case_id, correlation_id=case_id,
        subject="synthetic", user_token=scope().context.user_token,
        deadline_monotonic=asyncio.get_running_loop().time() + 30,
        cancellation=ManualCancellationSignal())


def id_map_raw(*, index_name: str, fingerprint: str,
               exclude: str | None = None, wrong_hash: str | None = None) -> bytes:
    records = []
    for domain in ("tax.policy", "tax.law"):
        for case_id in CASE_IDS:
            for prefix in ("keyword", "keyword-changed", "required", "vector-unrelated"):
                chunk_id = f"{prefix}-{case_id}-{domain}"
                if chunk_id == exclude:
                    continue
                item = candidate(chunk=chunk_id, domain=domain)
                records.append({"id": chunk_id, "documentId": item.document_id,
                    "chunkId": item.chunk_id,
                    "contentSha256": wrong_hash if chunk_id == f"required-{CASE_IDS[0]}-tax.policy"
                        and wrong_hash is not None else item.content_sha256})
    records.sort(key=lambda item: item["id"])
    value = {"schemaVersion": 1, "indexName": index_name, "indexUuid": index_name + "Uuid",
             "sourceFingerprint": fingerprint, "recordCount": len(records), "records": records}
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def id_map(*, index_name: str, fingerprint: str, **changes) -> FrozenIdMapping:
    raw = id_map_raw(index_name=index_name, fingerprint=fingerprint, **changes)
    return FrozenIdMapping.from_bytes(raw, expected_sha256=hashlib.sha256(raw).hexdigest())


def endpoint(search: FakeSearch, *, arm: str, exclude: str | None = None,
             wrong_hash: str | None = None) -> ArmEndpoint:
    return ArmEndpoint(search=search, snapshots=snapshots(arm),
        id_mapping=id_map(index_name=f"full-{arm}",
            fingerprint="1" * 64 if arm == "baseline" else "2" * 64,
            exclude=exclude, wrong_hash=wrong_hash))


def provenance_sidecars(frozen: ComparisonSpec, baseline: ArmEndpoint,
                        proposed: ArmEndpoint) -> dict[str, bytes]:
    source = frozen.source_corpus
    run_id = "synthetic-b-compare-run"
    pages = (source.record_count + 249) // 250
    per_arm = 1 + pages
    scan_budget = {"sourceEsHttp": per_arm, "candidateEsHttp": per_arm,
                   "retry": 0, "resume": 0}
    update = baseline.id_mapping.records[0]
    row = {"identifier": update.es_id, "document_id": update.document_id,
           "parent_document_id": "synthetic-parent", "asset_id": "synthetic-asset",
           "asset_version": "3" * 64, "version": "body-only-v2",
           "input_sha256": update.content_sha256, "body_sha256": update.content_sha256}
    model = {"container": {"id": "synthetic-bge", "image": "synthetic-image",
                           "started": "2026-09-29T00:00:00Z", "running": True,
                           "path": "synthetic-path", "args": [], "ports": []},
             "model": {"revision": "synthetic-stable", "files": [],
                       "service": "synthetic", "implementation": "synthetic",
                       "max_length": 512, "packages": [], "cache_provenance": "synthetic"}}
    budget = {"esHttp": 42 + 4 * pages + 3, "embeddingHttp": 1, "writeOps": 1,
              "paid": 0, "retry": 0, "resume": 0,
              "onlineAliasWrites": 0, "candidates": 1}
    canonical = lambda value: (json.dumps(value, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")) + "\n").encode()
    digest = lambda value: hashlib.sha256(canonical(value)).hexdigest()
    scan_plan = {
        "schemaVersion": 2, "kind": "knowledge_b_mapping_scan_plan_v2", "runId": run_id,
        "frozenHead": "a" * 40, "branch": "codex_0915",
        "assessmentIntentSha256": frozen.assessment_intent_sha256,
        "fixtureGitBlobSha256": frozen.uat_fixture_sha256,
        "requestCoreSha256": "4" * 64,
        "sourceIndex": source.index_name, "sourceUuid": source.index_uuid,
        "sourceCount": source.record_count, "sourceMappingSha256": source.mapping_sha256,
        "sourceFingerprint": source.full_fingerprint,
        "candidateIndex": proposed.id_mapping.index_name,
        "candidateMappingSha256": "f" * 64,
        "mappingScanBudget": scan_budget,
    }
    results = {}
    for arm, item in (("source", baseline), ("candidate", proposed)):
        mapping = item.id_mapping
        results[f"{arm}ScanResult"] = {"schemaVersion": 2, "arm": arm,
            "assessmentIntentSha256": frozen.assessment_intent_sha256,
            "status": "scanned_read_only", "reason": None,
            "indexName": mapping.index_name, "indexUuid": mapping.index_uuid,
            "mappingVersion": ("synthetic-baseline-map-v1" if arm == "source"
                               else "synthetic-mapping-v1"),
            "sourceFingerprint": mapping.source_fingerprint,
            "sha256": mapping.sha256, "recordCount": source.record_count,
            "esHttp": per_arm, "maxEsHttp": per_arm, "retry": 0, "resume": 0}
    binding = {
        "schemaVersion": 2, "kind": "knowledge_b_representation_candidate_v2",
        "runId": run_id, "frozenHead": "a" * 40,
        "branch": "codex_0915", "sourceVerification": "pending_builder_live_preflight",
        "assessmentIntentSha256": frozen.assessment_intent_sha256,
        "idMappingSha256": baseline.id_mapping.sha256,
        "idMappingSourceFingerprint": source.full_fingerprint,
        "freezeInputSha256": "5" * 64,
        "scanPlanSha256": digest(scan_plan),
        "sourceMapScanResultSha256": digest(results["sourceScanResult"]),
        "spec": {"source_index": source.index_name, "source_uuid": source.index_uuid,
                 "source_count": source.record_count,
                 "source_mapping_sha256": source.mapping_sha256,
                 "source_fingerprint": source.full_fingerprint,
                 "candidate_index": proposed.id_mapping.index_name,
                 "target_mapping_sha256": "f" * 64,
                 "read_alias": "synthetic-read-alias",
                 "online_index": source.index_name,
                 "online_uuid": source.index_uuid,
                 "online_mapping_sha256": source.mapping_sha256,
                 "alias_snapshot_sha256": "7" * 64,
                 "target_mapping_version": "synthetic-mapping-v1",
                 "workspace": "D:/synthetic-b-run",
                 "mode": "representation", "changes": [],
                 "update_ids": [update.es_id],
                 "representation_scope": [{"identifier": update.es_id,
                     "document_id": update.document_id,
                     "parent_document_id": row["parent_document_id"],
                     "asset_id": row["asset_id"],
                     "asset_version": row["asset_version"]}],
                 "representation_binding_sha256": digest([[update.es_id, "body-only-v2",
                     update.content_sha256, update.content_sha256]]),
                 "baseline_representation_version": "policy-title-section-body-v1",
                 "representation_version": "body-only-v2",
                 "tokenizer_sha256": "6" * 64,
                 "baseline_model_snapshot": model, "model_snapshot": model,
                 "baseline_model_snapshot_sha256": digest(model),
                 "model_snapshot_sha256": digest(model),
                 "assessment_intent_sha256": frozen.assessment_intent_sha256,
                 "max_http_requests": budget["esHttp"], "max_embedding_requests": 1,
                 "max_write_ops": 1},
        "representationBindings": [row], "budget": budget,
        "mappingScanBudget": scan_budget,
    }
    preliminary = {"schemaVersion": 2, "runId": run_id,
                   "frozenHead": scan_plan["frozenHead"],
                   "assessmentIntentSha256": frozen.assessment_intent_sha256,
                   "candidate": {key: binding["spec"][key] for key in CANDIDATE_INPUT_KEYS},
                   "representationBindings": [row], "budget": budget,
                   "mappingScanBudget": scan_budget}
    scan_plan["requestCoreSha256"] = digest(preliminary)
    binding["freezeInputSha256"] = digest({**preliminary,
                                           "idMappingSha256": baseline.id_mapping.sha256})
    binding["scanPlanSha256"] = digest(scan_plan)
    built = {"schemaVersion": 2, "runId": run_id,
             "assessmentIntentSha256": frozen.assessment_intent_sha256,
             "bindingSha256": digest(binding), "status": "built_read_only_unpublished",
             "sourceVerifiedByBuilder": True,
             "candidateMapping": "pending_postbuild_readonly_scan",
             "executionKind": "fake", "paid": 0, "retry": 0, "resume": 0,
             "onlineAliasWrites": 0, "updatedCount": 1,
             "esHttp": budget["esHttp"], "embeddingHttp": 1,
             "candidateIndex": proposed.id_mapping.index_name,
             "candidateUuid": proposed.id_mapping.index_uuid,
             "candidateFingerprint": proposed.id_mapping.source_fingerprint,
             "candidateCount": source.record_count}
    values = {"scanPlan": scan_plan, "binding": binding,
              "builderResult": built, **results}
    return {key: canonical(value) for key, value in values.items()}


async def execute(*, keyword_drift: bool = False, denied: bool = False,
                  invalid_vector: bool = False, exclude: str | None = None,
                  wrong_hash: str | None = None, no_result: bool = False):
    events: list[tuple[str, str]] = []
    baseline = FakeSearch("baseline", no_result=no_result, events=events)
    proposed = FakeSearch("candidate", keyword_drift=keyword_drift, denied=denied,
                          no_result=no_result, events=events)
    embedding = FakeEmbedding(invalid=invalid_vector)
    rerank = FakeRerank()
    result = await run_comparison(spec=spec(),
        baseline=(base_endpoint := endpoint(baseline, arm="baseline", exclude=exclude,
                                            wrong_hash=wrong_hash)),
        candidate=(candidate_endpoint := endpoint(proposed, arm="candidate", exclude=exclude,
                                                  wrong_hash=wrong_hash)),
        embedding=embedding, rerank=rerank, context_for=context_for,
        provenance_sidecars=provenance_sidecars(spec(), base_endpoint, candidate_endpoint),
        clock=TickClock())
    return result, baseline, proposed, embedding, rerank


async def test_shared_embedding_alternating_arms_typed_stage_and_budgets():
    result, baseline, proposed, embedding, rerank = await execute()
    assert len(result.cases) == 10 and result.calls.typed_search == 44
    assert result.calls.query_embedding == 10 and result.calls.online_rerank == 22
    assert len(embedding.calls) == 10 and rerank.calls == 22
    assert len(baseline.calls) == len(proposed.calls) == 22
    assert baseline.contexts[0] is proposed.contexts[0]
    assert all(next(context for context in baseline.contexts if context.request_id == case_id)
               is next(context for context in proposed.contexts if context.request_id == case_id)
               for case_id in CASE_IDS)
    assert baseline.events[0][1] == "baseline"
    assert next(arm for case_id, arm in baseline.events if case_id == CASE_IDS[1]) == "candidate"
    assert result.cases[0].baseline.keyword[0].ranked == result.cases[0].candidate.keyword[0].ranked
    assert result.cases[0].baseline.keyword_es_ids == result.cases[0].candidate.keyword_es_ids
    assert result.cases[0].baseline.final20 != result.cases[0].candidate.final20
    assert all(arm.latency_seconds > 0 for row in result.cases for arm in (row.baseline, row.candidate))
    # The second frozen case is run candidate-first, but the returned trace retains stable arm names.
    assert result.cases[1].case_id == CASE_IDS[1]
    assert len(result.cases[5].baseline.keyword) == 2  # policy and law, not one unconditional domain


async def test_blind_pool_and_exact_actual_returned_scoring():
    result, *_ = await execute()
    pool = blind_label_pool(result)
    assert len(pool) <= 400 and len(pool) == len(set(pool))
    assert all(len(key) == 4 and key[0] in CASE_IDS for key in pool)
    labels = {key: key[2].startswith("required-") for key in pool}
    scored = score_comparison(spec=spec(), run=result, labels=labels)
    assert scored.outcome == "not_assessed" and scored.reasons == ("synthetic_only",)
    assert scored.macro_candidate_recall > scored.macro_baseline_recall
    assert scored.macro_candidate_precision > scored.macro_baseline_precision
    first = scored.case_metrics[0]
    assert first.baseline_recall == 0.0 and first.candidate_recall == 1.0
    # Two returned candidates, not fixed k=20: one relevant means 1/2.
    assert first.candidate_precision == 0.5
    assert any(stage == "final20" and ranks == (1,) or stage == "final20" and ranks == (2,)
               for _, stage, ranks in first.stage_required_ranks)


async def test_fake_score_cannot_be_relabeled_as_real_evidence():
    result, *_ = await execute()
    assert result.evidence_kind == "synthetic_only"
    labels = {key: True for key in blind_label_pool(result)}
    with pytest.raises(ValueError, match="comparison_invalid"):
        score_comparison(spec=spec(), run=replace(result, evidence_kind="verified_real"),
                         labels=labels)


async def test_local_builder_without_isolated_runtime_provenance_stops_at_preflight():
    frozen = spec()
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)
    built = json.loads(sidecars["builderResult"])
    built["executionKind"] = "local"
    sidecars["builderResult"] = canonical(built)
    final = json.loads(frozen.final_raw)
    final["builderResultSha256"] = hashlib.sha256(sidecars["builderResult"]).hexdigest()
    final_raw = canonical(final)
    frozen = replace(frozen, final_raw=final_raw,
                     assessment_sha256=hashlib.sha256(final_raw).hexdigest())
    embedding = FakeEmbedding()
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=frozen, baseline=baseline, candidate=proposed,
            embedding=embedding, rerank=FakeRerank(), context_for=context_for,
            provenance_sidecars=sidecars)
    assert caught.value.reason == "runtime_provenance_missing"
    assert caught.value.outcome == "not_assessed"
    assert caught.value.stage == "preflight"
    assert caught.value.unexecuted_case_ids == CASE_IDS
    assert (caught.value.calls.typed_search, caught.value.calls.query_embedding,
            caught.value.calls.online_rerank) == (0, 0, 0)
    assert embedding.calls == []


async def test_score_rejects_run_from_changed_gold_or_fixture():
    result, *_ = await execute()
    labels = {key: True for key in blind_label_pool(result)}
    with pytest.raises(ValueError, match="comparison_invalid"):
        score_comparison(spec=replace(spec(), assessment_sha256="f" * 64),
                         run=result, labels=labels)
    with pytest.raises(ValueError, match="comparison_invalid"):
        score_comparison(spec=replace(spec(), uat_fixture_sha256="f" * 64),
                         run=result, labels=labels)
    forged = spec()
    changed_case = replace(forged.cases[0], necessary_sources=(
        required(CASE_IDS[1]),))
    with pytest.raises(ValueError, match="comparison_invalid"):
        score_comparison(spec=replace(forged, cases=(changed_case, *forged.cases[1:])),
                         run=result, labels=labels)


async def test_missing_blind_label_is_not_treated_as_negative_or_dropped():
    result, *_ = await execute()
    pool = blind_label_pool(result)
    labels = {key: True for key in pool[1:]}
    scored = score_comparison(spec=spec(), run=result, labels=labels)
    assert scored.outcome == "not_assessed" and scored.unjudged_count == 1
    assert scored.macro_baseline_precision is None and scored.macro_candidate_precision is None
    assert scored.macro_candidate_recall is not None
    with pytest.raises(ValueError, match="comparison_invalid"):
        score_comparison(spec=spec(), run=result, labels={("foreign", "d", "c", "a" * 64): True})


async def test_keyword_order_drift_confounds_even_if_final_recall_improves():
    result, *_ = await execute(keyword_drift=True)
    pool = blind_label_pool(result)
    score = score_comparison(spec=spec(), run=result, labels={key: True for key in pool})
    assert score.outcome == "not_assessed"
    assert "keyword_order_confounded:UAT-KM-001:tax.policy" in score.reasons
    assert score.macro_candidate_recall > score.macro_baseline_recall


async def test_no_result_is_scored_zero_without_retrieval_failure_or_rerank():
    result, _, _, _, rerank = await execute(no_result=True)
    assert result.cases[0].baseline.final20 == result.cases[0].candidate.final20 == ()
    assert result.calls.online_rerank == rerank.calls == 20
    scored = score_comparison(spec=spec(), run=result,
                              labels={key: True for key in blind_label_pool(result)})
    assert scored.case_metrics[0].baseline_recall == scored.case_metrics[0].candidate_recall == 0
    assert scored.case_metrics[0].baseline_precision == scored.case_metrics[0].candidate_precision == 0
    assert scored.outcome == "not_assessed" and "recall_not_improved" in scored.reasons


async def test_latency_regression_uses_per_arm_median_not_total_batch_time():
    result, *_ = await execute()
    changed = replace(result, cases=tuple(replace(case,
        candidate=replace(case.candidate, latency_seconds=case.candidate.latency_seconds * 2))
        for case in result.cases))
    scored = score_comparison(spec=spec(), run=changed,
                              labels={key: True for key in blind_label_pool(result)})
    assert scored.outcome == "not_assessed" and "latency_regression" in scored.reasons


@pytest.mark.parametrize("change", [
    {"exclude": f"required-{CASE_IDS[0]}-tax.policy"},
    {"wrong_hash": "f" * 64},
])
async def test_missing_or_content_drift_in_frozen_id_map_is_not_assessed(change):
    with pytest.raises(ComparisonRunError) as caught:
        await execute(**change)
    assert caught.value.reason == "source_id_mapping_confounded"
    assert caught.value.outcome == "not_assessed"
    assert len(caught.value.completed) == 0
    assert caught.value.calls.typed_search == caught.value.calls.query_embedding == 0


async def test_mapping_mismatch_stops_before_rerank_or_later_cases():
    baseline = FakeSearch("baseline")
    proposed = FakeSearch("candidate")
    rerank = FakeRerank()
    baseline_endpoint = endpoint(baseline, arm="baseline", wrong_hash="f" * 64)
    candidate_endpoint = endpoint(proposed, arm="candidate", wrong_hash="f" * 64)
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=spec(),
            baseline=baseline_endpoint, candidate=candidate_endpoint,
            embedding=FakeEmbedding(), rerank=rerank, context_for=context_for,
            provenance_sidecars=provenance_sidecars(spec(), baseline_endpoint,
                                                    candidate_endpoint))
    assert caught.value.reason == "source_id_mapping_confounded"
    assert caught.value.completed == ()
    assert caught.value.calls.query_embedding == 0
    assert rerank.calls == 0
    assert caught.value.case_id is None
    assert caught.value.stage == "preflight"
    assert caught.value.unexecuted_case_ids == CASE_IDS


def test_duplicate_or_noncanonical_frozen_map_is_not_assessed_before_calls():
    raw = id_map_raw(index_name="synthetic", fingerprint="1" * 64)
    value = json.loads(raw)
    value["records"].append(value["records"][-1])
    value["recordCount"] += 1
    duplicate = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(ComparisonRunError) as caught:
        FrozenIdMapping.from_bytes(duplicate, expected_sha256=hashlib.sha256(duplicate).hexdigest())
    assert caught.value.outcome == "not_assessed" and caught.value.calls.typed_search == 0
    value["records"][-1] = {**value["records"][-1], "id": "zzzz-new-id"}
    duplicate_source = (json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")) + "\n").encode()
    with pytest.raises(ComparisonRunError) as caught:
        FrozenIdMapping.from_bytes(duplicate_source,
                                   expected_sha256=hashlib.sha256(duplicate_source).hexdigest())
    assert caught.value.outcome == "not_assessed"
    with pytest.raises(ComparisonRunError) as caught:
        FrozenIdMapping.from_bytes(raw[:-1], expected_sha256=hashlib.sha256(raw[:-1]).hexdigest())
    assert caught.value.outcome == "not_assessed"


async def test_denied_stops_batch_without_later_cases_or_raw_response():
    with pytest.raises(ComparisonRunError) as caught:
        await execute(denied=True)
    error = caught.value
    assert error.reason == "comparison_execution_failed" and error.completed == ()
    assert error.calls.query_embedding == 1 and error.calls.typed_search <= 4
    assert "公开税务资料" not in str(error)


async def test_invalid_embedding_zero_typed_and_no_rerank():
    with pytest.raises(ComparisonRunError) as caught:
        await execute(invalid_vector=True)
    assert caught.value.calls.query_embedding == 1
    assert caught.value.calls.typed_search == caught.value.calls.online_rerank == 0


def test_spec_rejects_duplicate_or_over_budget_before_any_port_is_called():
    good = spec()
    with pytest.raises(ValueError, match="comparison_invalid"):
        replace(good, cases=good.cases[:-1] + (good.cases[0],))
    oversized = tuple(replace(case, plan=make_plan(("tax.policy", "tax.law"),
        question=f"查询公开税务资料 {case.case_id}")) for case in good.cases)
    with pytest.raises(ValueError, match="comparison_invalid"):
        replace(good, cases=oversized)


async def test_snapshot_or_policy_drift_fails_closed_before_scoring():
    baseline = FakeSearch("baseline")
    proposed = FakeSearch("candidate")
    wrong = endpoint(proposed, arm="candidate")
    wrong = replace(wrong, snapshots=(("tax.policy", "b" * 64), ("tax.law", "d" * 64)))
    base_endpoint = endpoint(baseline, arm="baseline")
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=spec(),
            baseline=base_endpoint, candidate=wrong,
            embedding=FakeEmbedding(), rerank=FakeRerank(), context_for=context_for,
            provenance_sidecars=provenance_sidecars(spec(), base_endpoint, wrong))
    assert caught.value.outcome == "not_assessed" and caught.value.calls.query_embedding == 0


async def test_two_arm_mapping_drift_is_not_assessed_before_any_call():
    baseline = FakeSearch("baseline")
    proposed = FakeSearch("candidate")
    base_endpoint = endpoint(baseline, arm="baseline")
    candidate_endpoint = endpoint(proposed, arm="candidate", wrong_hash="f" * 64)
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=spec(), baseline=base_endpoint,
            candidate=candidate_endpoint, embedding=FakeEmbedding(), rerank=FakeRerank(),
            context_for=context_for,
            provenance_sidecars=provenance_sidecars(spec(), base_endpoint, candidate_endpoint))
    assert caught.value.reason == "source_id_mapping_confounded"
    assert caught.value.calls.typed_search == caught.value.calls.query_embedding == 0
    assert caught.value.stage == "preflight"
    assert caught.value.unexecuted_case_ids == CASE_IDS


@pytest.mark.parametrize("drift", ["builder_uuid", "source_scan_count", "scan_budget",
                                   "source_mapping_version", "candidate_scan_uuid"])
async def test_sidecar_binding_drift_stops_before_any_port_call(drift):
    frozen = spec()
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)
    key = {"builder_uuid": "builderResult", "source_scan_count": "sourceScanResult",
           "scan_budget": "scanPlan", "source_mapping_version": "sourceScanResult",
           "candidate_scan_uuid": "candidateScanResult"}[drift]
    value = json.loads(sidecars[key])
    if drift == "builder_uuid":
        value["candidateUuid"] = "forged-uuid"
    elif drift == "source_scan_count":
        value["recordCount"] = 79
    elif drift == "source_mapping_version":
        value["mappingVersion"] = "unbound-map-v1"
    elif drift == "candidate_scan_uuid":
        value["indexUuid"] = "forged-uuid"
    else:
        value["mappingScanBudget"]["sourceEsHttp"] = 3
    sidecars[key] = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":")) + "\n").encode()
    embedding = FakeEmbedding()
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=frozen, baseline=baseline, candidate=proposed,
            embedding=embedding, rerank=FakeRerank(), context_for=context_for,
            provenance_sidecars=sidecars)
    assert caught.value.reason == "source_id_mapping_confounded"
    assert caught.value.calls.query_embedding == caught.value.calls.typed_search == 0
    assert embedding.calls == []


@pytest.mark.parametrize("link", ["bindingSha256", "builderResultSha256",
    "sourceMapScanResultSha256", "candidateMapScanResultSha256",
    "sourceIdMappingSha256", "candidateIdMappingSha256"])
async def test_final_assessment_rejects_rebound_sidecars_before_any_port_call(link):
    frozen = spec()
    changed = json.loads(frozen.final_raw)
    changed[link] = "0" * 64
    raw = canonical(changed)
    frozen = replace(frozen, final_raw=raw, assessment_sha256=hashlib.sha256(raw).hexdigest())
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    embedding = FakeEmbedding()
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=frozen, baseline=baseline, candidate=proposed,
            embedding=embedding, rerank=FakeRerank(), context_for=context_for,
            provenance_sidecars=provenance_sidecars(frozen, baseline, proposed))
    assert caught.value.reason == "source_id_mapping_confounded"
    assert caught.value.stage == "preflight"
    assert (caught.value.calls.typed_search, caught.value.calls.query_embedding,
            caught.value.calls.online_rerank) == (0, 0, 0)
    assert embedding.calls == []


@pytest.mark.parametrize("drift", [
    "builder_binding_hash", "scan_plan_hash", "source_scan_hash",
    "request_core_hash", "freeze_input_hash",
    "representation_version", "update_ids", "representation_binding_hash",
    "model_snapshot", "tokenizer_hash", "budget",
])
async def test_forged_provenance_or_frozen_representation_stops_preflight(drift):
    frozen = spec()
    baseline = endpoint(FakeSearch("baseline"), arm="baseline")
    proposed = endpoint(FakeSearch("candidate"), arm="candidate")
    sidecars = provenance_sidecars(frozen, baseline, proposed)

    def canonical(value):
        return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")) + "\n").encode()

    if drift == "builder_binding_hash":
        built = json.loads(sidecars["builderResult"])
        built["bindingSha256"] = "0" * 64
        sidecars["builderResult"] = canonical(built)
    else:
        binding = json.loads(sidecars["binding"])
        scan_plan = json.loads(sidecars["scanPlan"])
        if drift == "scan_plan_hash":
            binding["scanPlanSha256"] = "0" * 64
        elif drift == "source_scan_hash":
            binding["sourceMapScanResultSha256"] = "0" * 64
        elif drift == "request_core_hash":
            scan_plan["requestCoreSha256"] = "0" * 64
            binding["scanPlanSha256"] = hashlib.sha256(canonical(scan_plan)).hexdigest()
        elif drift == "freeze_input_hash":
            binding["freezeInputSha256"] = "0" * 64
        elif drift == "representation_version":
            binding["spec"]["representation_version"] = "trusted-title-section-body-v2"
        elif drift == "update_ids":
            binding["spec"]["update_ids"] = ["forged-id"]
        elif drift == "representation_binding_hash":
            binding["spec"]["representation_binding_sha256"] = "0" * 64
        elif drift == "model_snapshot":
            model = binding["spec"]["model_snapshot"]
            model["model"]["revision"] = "changed"
            binding["spec"]["model_snapshot_sha256"] = hashlib.sha256(
                canonical(model)).hexdigest()
        elif drift == "tokenizer_hash":
            binding["spec"]["tokenizer_sha256"] = "not-a-hash"
        else:
            binding["budget"]["writeOps"] = 2
        if drift in {"representation_version", "update_ids", "representation_binding_hash",
                     "model_snapshot", "tokenizer_hash", "budget"}:
            preliminary = {"schemaVersion": 2, "runId": binding["runId"],
                           "frozenHead": binding["frozenHead"],
                           "assessmentIntentSha256": binding["assessmentIntentSha256"],
                           "candidate": {key: binding["spec"][key]
                                         for key in CANDIDATE_INPUT_KEYS},
                           "representationBindings": binding["representationBindings"],
                           "budget": binding["budget"],
                           "mappingScanBudget": binding["mappingScanBudget"]}
            scan_plan["requestCoreSha256"] = hashlib.sha256(canonical(preliminary)).hexdigest()
            binding["freezeInputSha256"] = hashlib.sha256(canonical({
                **preliminary, "idMappingSha256": binding["idMappingSha256"]})).hexdigest()
            binding["scanPlanSha256"] = hashlib.sha256(canonical(scan_plan)).hexdigest()
        sidecars["scanPlan"] = canonical(scan_plan)
        sidecars["binding"] = canonical(binding)
        built = json.loads(sidecars["builderResult"])
        built["bindingSha256"] = hashlib.sha256(sidecars["binding"]).hexdigest()
        sidecars["builderResult"] = canonical(built)

    embedding = FakeEmbedding()
    with pytest.raises(ComparisonRunError) as caught:
        await run_comparison(spec=frozen, baseline=baseline, candidate=proposed,
            embedding=embedding, rerank=FakeRerank(), context_for=context_for,
            provenance_sidecars=sidecars)
    assert caught.value.reason == "source_id_mapping_confounded"
    assert caught.value.stage == "preflight"
    assert caught.value.calls.query_embedding == caught.value.calls.typed_search == 0
    assert embedding.calls == []
