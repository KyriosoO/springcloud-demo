"""Synthetic-only, injected-port B comparison; never opens a service connection.

The runner uses the current MinimalKnowledgeRetrievalStage for both arms.  Its
cached embedding port returns one already validated query vector to both arms;
only the injected embedding port can perform the single real inference per case.
All returned records contain identities and hashes, never corpus text or vectors.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
import statistics
import time
from typing import cast

from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath, RetrievalStageKind
from agent_runtime.knowledge.minimal_plan import MinimalKnowledgeRetrievalPlan
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate, EmbeddingPort, KnowledgePathRequest, KnowledgeSearchPort,
    PathCandidateSet, PathResultKind, PathRetrievalResult, RerankPort, RerankScore,
)
from agent_runtime.knowledge.retrieval.fusion import ReciprocalRankFusion
from agent_runtime.knowledge.retrieval.minimal_ranking import domain_pool, order_domain, round_robin
from agent_runtime.knowledge.retrieval.minimal_stage import MinimalKnowledgeRetrievalStage, _candidate_set


_SAFE_ID = re.compile(r"[A-Za-z0-9._:@#-]{1,256}")
_SHA = re.compile(r"[0-9a-f]{64}")
_CASE = re.compile(r"UAT-KM-[0-9]{3}")
_ARMS = ("baseline", "candidate")
_DOMAINS = ("tax.policy", "tax.law")
_RETRIEVAL_CASE_IDS = tuple(f"UAT-KM-{number:03d}" for number in
                            (1, 2, 3, 5, 6, 7, 8, 9, 11, 12))
_THRESHOLDS: dict[str, object] = {
    "macroRecallStrictlyImproves": True,
    "macroPrecisionNoRegression": True,
    "medianLatencyRatioMax": 1.10,
    "coreAndRetainedNoRegression": True,
    "missingBlindLabel": "not_assessed",
    "unexplainedKeywordDrift": "not_assessed",
}
_INTENT_KEYS = frozenset({
    "schemaVersion", "kind", "uatFixtureSha256", "source", "candidate",
    "profileParameters", "baselineProfileSnapshots", "builderBudget",
    "mappingScanBudget", "comparisonBudget", "representationBindings",
    "modelBindings", "sourceBuildEvidence", "cases", "thresholds",
})
_SOURCE_BUILD_DIRECTORY = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2"
_FINAL_KEYS = frozenset({
    "schemaVersion", "kind", "assessmentIntentSha256", "bindingSha256",
    "builderResultSha256", "sourceMapScanResultSha256", "candidateMapScanResultSha256",
    "sourceIdMappingSha256", "candidateIdMappingSha256", "candidateIdentity",
    "candidateProfileSnapshots",
})
_PROFILE_PARAMETER_KEYS = frozenset({
    "profileId", "profileVersion", "readPolicyVersion", "baselineMappingVersion",
    "candidateMappingVersion", "configSha256",
})
_MODEL_BINDING_KEYS = frozenset({
    "baselineModelSnapshotSha256", "currentModelSnapshotSha256", "tokenizerSha256",
    "baselineRepresentationVersion", "candidateRepresentationVersion",
})
_COMPARISON_BUDGET_FIXED = {"typedSearch": 44, "queryEmbedding": 10, "rerank": 22,
                            "aliasWrites": 4, "paid": 0, "retry": 0, "resume": 0}
MAX_TYPED = 48
MAX_EMBED = 12
MAX_RERANK = 24


def _invalid() -> ValueError:
    return ValueError("knowledge.rebuild_b_comparison_invalid")


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def plan_payload(plan: MinimalKnowledgeRetrievalPlan) -> dict[str, object]:
    """Canonical public-to-the-evaluator shape of the frozen retrieval plan."""
    if type(plan) is not MinimalKnowledgeRetrievalPlan:
        raise _invalid()
    plan.validate(plan.settings)
    settings = plan.settings
    return {
        "schemaVersion": plan.schema_version,
        "catalogVersion": plan.catalog_version,
        "originalQuestion": plan.original_question,
        "queryMode": plan.query_mode.value,
        "selectedDomainIds": list(plan.selected_domain_ids),
        "profileBindings": [list(binding) for binding in plan.profile_bindings],
        "settings": {
            "enabledDomainIds": list(settings.enabled_domain_ids),
            "perPathCandidateLimit": settings.per_path_candidate_limit,
            "finalCandidateLimit": settings.final_candidate_limit,
            "minPartialCandidates": settings.min_partial_candidates,
            "retrievalTimeoutSeconds": settings.retrieval_timeout_s,
            "configVersion": settings.config_version,
        },
        "items": [{
            "logicalDomainId": item.logical_domain_id,
            "path": item.path.value,
            "queryText": item.query_text,
            "candidateLimit": item.candidate_limit,
            "ordinal": item.ordinal,
        } for item in plan.items],
    }


def plan_fingerprint(plan: MinimalKnowledgeRetrievalPlan) -> str:
    """Bind the precise request-local production plan, not just its question."""
    return hashlib.sha256(_canonical_bytes(plan_payload(plan))).hexdigest()


def _profile_snapshot(profile_id: str, index_name: str, index_uuid: str,
                      profile_version: str, mapping_version: str) -> str:
    return hashlib.sha256("\n".join((profile_id, index_name, index_uuid,
        profile_version, mapping_version)).encode("utf-8")).hexdigest()


def _valid_comparison_budget(value: object) -> bool:
    return (type(value) is dict
            and set(value) == {*_COMPARISON_BUDGET_FIXED, "metadataEsHttp"}
            and all(type(value[key]) is int and value[key] == expected
                    for key, expected in _COMPARISON_BUDGET_FIXED.items())
            and type(value["metadataEsHttp"]) is int
            and 1 <= value["metadataEsHttp"] <= 512)


@dataclass(frozen=True, slots=True, order=True)
class CandidateRef:
    document_id: str
    chunk_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        if (type(self.document_id) is not str or _SAFE_ID.fullmatch(self.document_id) is None
                or type(self.chunk_id) is not str or _SAFE_ID.fullmatch(self.chunk_id) is None
                or type(self.content_sha256) is not str or _SHA.fullmatch(self.content_sha256) is None):
            raise _invalid()

    @classmethod
    def from_candidate(cls, candidate: AuthorizedKnowledgeCandidate) -> CandidateRef:
        return cls(candidate.document_id, candidate.chunk_id, candidate.content_sha256)


@dataclass(frozen=True, slots=True)
class ComparisonCase:
    case_id: str
    plan: MinimalKnowledgeRetrievalPlan = field(repr=False)
    necessary_sources: tuple[CandidateRef, ...]
    core: bool
    retained: bool

    def __post_init__(self) -> None:
        if (type(self.case_id) is not str or _CASE.fullmatch(self.case_id) is None
                or type(self.plan) is not MinimalKnowledgeRetrievalPlan
                or type(self.necessary_sources) is not tuple or not self.necessary_sources
                or any(type(item) is not CandidateRef for item in self.necessary_sources)
                or len(set(self.necessary_sources)) != len(self.necessary_sources)
                or type(self.core) is not bool or type(self.retained) is not bool):
            raise _invalid()
        self.plan.validate(self.plan.settings)


@dataclass(frozen=True, slots=True)
class SourceCorpusBinding:
    index_name: str
    index_uuid: str
    record_count: int
    mapping_sha256: str
    full_fingerprint: str

    def __post_init__(self) -> None:
        if (type(self.index_name) is not str or _SAFE_ID.fullmatch(self.index_name) is None
                or type(self.index_uuid) is not str or _SAFE_ID.fullmatch(self.index_uuid) is None
                or type(self.record_count) is not int or not 1 <= self.record_count <= 22000
                or type(self.mapping_sha256) is not str or _SHA.fullmatch(self.mapping_sha256) is None
                or type(self.full_fingerprint) is not str or _SHA.fullmatch(self.full_fingerprint) is None):
            raise _invalid()


@dataclass(frozen=True, slots=True)
class ComparisonSpec:
    cases: tuple[ComparisonCase, ...]
    profile_snapshots: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    uat_fixture_sha256: str
    assessment_intent_sha256: str
    assessment_sha256: str
    source_corpus: SourceCorpusBinding
    candidate_corpus: SourceCorpusBinding
    intent_raw: bytes = field(repr=False)
    final_raw: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if (type(self.cases) is not tuple or len(self.cases) != 10
                or any(type(case) is not ComparisonCase for case in self.cases)
                or len({case.case_id for case in self.cases}) != 10
                or any(case.plan.settings != self.cases[0].plan.settings for case in self.cases)
                or any(not case.retained for case in self.cases)
                or not any(case.core for case in self.cases)
                or sum(len(case.plan.items) for case in self.cases) * 2 > MAX_TYPED
                or sum(len(case.plan.selected_domain_ids) for case in self.cases) * 2 > MAX_RERANK
                or type(self.profile_snapshots) is not tuple
                or tuple(arm for arm, _ in self.profile_snapshots) != _ARMS
                or any(tuple(domain for domain, _ in entries) != _DOMAINS
                       or any(type(snapshot) is not str or _SHA.fullmatch(snapshot) is None
                              for _, snapshot in entries)
                       for _, entries in self.profile_snapshots)
                or any(dict(self.profile_snapshots)["baseline"][index][1]
                       == dict(self.profile_snapshots)["candidate"][index][1]
                       for index in range(len(_DOMAINS)))
                or type(self.uat_fixture_sha256) is not str
                or _SHA.fullmatch(self.uat_fixture_sha256) is None
                or type(self.assessment_intent_sha256) is not str
                or _SHA.fullmatch(self.assessment_intent_sha256) is None
                or type(self.assessment_sha256) is not str
                or _SHA.fullmatch(self.assessment_sha256) is None
                or type(self.source_corpus) is not SourceCorpusBinding
                or type(self.candidate_corpus) is not SourceCorpusBinding
                or self.source_corpus.index_name == self.candidate_corpus.index_name
                or self.source_corpus.index_uuid == self.candidate_corpus.index_uuid
                or self.source_corpus.record_count != self.candidate_corpus.record_count
                or type(self.intent_raw) is not bytes
                or hashlib.sha256(self.intent_raw).hexdigest() != self.assessment_intent_sha256
                or type(self.final_raw) is not bytes
                or hashlib.sha256(self.final_raw).hexdigest() != self.assessment_sha256):
            raise _invalid()

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(domain for case in self.cases for domain in case.plan.selected_domain_ids))

    @classmethod
    def from_assessment_bytes(
        cls, raw: bytes, *, expected_sha256: str, intent_raw: bytes,
        expected_intent_sha256: str, uat_fixture_raw: bytes,
        authoritative_fixture_sha256: str,
        plans: Mapping[str, MinimalKnowledgeRetrievalPlan],
    ) -> ComparisonSpec:
        """Derive every case and source from the committed twelve-case fixture."""
        if (type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024
                or type(expected_sha256) is not str or _SHA.fullmatch(expected_sha256) is None
                or hashlib.sha256(raw).hexdigest() != expected_sha256
                or type(intent_raw) is not bytes or not 0 < len(intent_raw) <= 2 * 1024 * 1024
                or type(expected_intent_sha256) is not str
                or _SHA.fullmatch(expected_intent_sha256) is None
                or hashlib.sha256(intent_raw).hexdigest() != expected_intent_sha256
                or type(uat_fixture_raw) is not bytes or not 0 < len(uat_fixture_raw) <= 2 * 1024 * 1024
                or type(authoritative_fixture_sha256) is not str
                or _SHA.fullmatch(authoritative_fixture_sha256) is None
                or hashlib.sha256(uat_fixture_raw).hexdigest() != authoritative_fixture_sha256
                or not isinstance(plans, Mapping)):
            raise _invalid()
        try:
            final = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json,
                               parse_constant=_reject_constant)
            value = json.loads(intent_raw.decode("utf-8"), object_pairs_hook=_unique_json,
                               parse_constant=_reject_constant)
            fixture = json.loads(uat_fixture_raw.decode("utf-8"), object_pairs_hook=_unique_json,
                                 parse_constant=_reject_constant)
            if (type(value) is not dict or set(value) != _INTENT_KEYS
                    or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 2
                    or value["kind"] != "knowledge_b_assessment_intent_v2"
                    or type(value["uatFixtureSha256"]) is not str
                    or value["uatFixtureSha256"] != hashlib.sha256(uat_fixture_raw).hexdigest()
                    or type(value["cases"]) is not list or len(value["cases"]) != 10
                    or type(value["thresholds"]) is not dict
                    or set(value["thresholds"]) != set(_THRESHOLDS)
                    or any(type(value["thresholds"][key]) is not type(expected)
                           or value["thresholds"][key] != expected
                           for key, expected in _THRESHOLDS.items())
                    or intent_raw != _canonical_bytes(value)
                    or type(final) is not dict or set(final) != _FINAL_KEYS
                    or type(final["schemaVersion"]) is not int or final["schemaVersion"] != 2
                    or final["kind"] != "knowledge_b_retrieval_assessment_v2"
                    or final["assessmentIntentSha256"] != expected_intent_sha256
                    or raw != _canonical_bytes(final)):
                raise _invalid()
            if (type(fixture) is not dict or fixture.get("schemaVersion") != 1
                    or fixture.get("datasetId") != "knowledge-rebuild-measure-v1"
                    or type(fixture.get("sources")) is not list
                    or type(fixture.get("cases")) is not list
                    or type(fixture.get("sourceCorpus")) is not dict
                    or type(fixture.get("thresholds")) is not dict):
                raise _invalid()
            corpus = fixture["sourceCorpus"]
            source_binding = SourceCorpusBinding(corpus["index"], corpus["indexUuid"],
                corpus["recordCount"], corpus["mappingSha256"], corpus["fullFingerprint"])
            fixture_cases = fixture["cases"]
            if (len(fixture_cases) != 12
                    or tuple(item.get("caseId") for item in fixture_cases
                             if type(item) is dict) != tuple(f"UAT-KM-{number:03d}"
                                                         for number in range(1, 13))):
                raise _invalid()
            source_by_id: dict[str, dict[str, object]] = {}
            for source in fixture["sources"]:
                if (type(source) is not dict or type(source.get("id")) is not str
                        or source["id"] in source_by_id):
                    raise _invalid()
                source_by_id[source["id"]] = source
            frozen_cases = {item["caseId"]: item for item in fixture_cases}
            thresholds = fixture["thresholds"]
            core_ids = thresholds["uat"]["coreCases"]
            retained_ids = thresholds["comparisonB"]["retainedCases"]
            if (type(core_ids) is not list or type(retained_ids) is not list
                    or retained_ids != list(_RETRIEVAL_CASE_IDS)
                    or tuple(item["caseId"] for item in fixture_cases
                             if item.get("retrievalDenominator") is True) != _RETRIEVAL_CASE_IDS):
                raise _invalid()
            declared_source = value["source"]
            declared_candidate = value["candidate"]
            identity = final["candidateIdentity"]
            if (type(declared_source) is not dict
                    or set(declared_source) != {"indexName", "indexUuid", "mappingSha256",
                                                "sourceFingerprint", "recordCount"}
                    or declared_source != {"indexName": source_binding.index_name,
                        "indexUuid": source_binding.index_uuid,
                        "mappingSha256": source_binding.mapping_sha256,
                        "sourceFingerprint": source_binding.full_fingerprint,
                        "recordCount": source_binding.record_count}
                    or type(declared_candidate) is not dict
                    or set(declared_candidate) != {"indexName", "mappingSha256", "mappingVersion"}
                    or type(declared_candidate["indexName"]) is not str
                    or _SAFE_ID.fullmatch(declared_candidate["indexName"]) is None
                    or declared_candidate["indexName"] == source_binding.index_name
                    or not _valid_hash(declared_candidate["mappingSha256"])
                    or type(declared_candidate["mappingVersion"]) is not str
                    or not declared_candidate["mappingVersion"]
                    or type(identity) is not dict
                    or set(identity) != {"indexName", "indexUuid", "mappingSha256",
                                            "sourceFingerprint", "recordCount"}
                    or identity["indexName"] != declared_candidate["indexName"]
                    or identity["mappingSha256"] != declared_candidate["mappingSha256"]
                    or identity["recordCount"] != source_binding.record_count):
                raise _invalid()
            candidate_binding = SourceCorpusBinding(identity["indexName"], identity["indexUuid"],
                identity["recordCount"], identity["mappingSha256"], identity["sourceFingerprint"])
            parameters = value["profileParameters"]
            baseline_snapshots = value["baselineProfileSnapshots"]
            candidate_snapshots = final["candidateProfileSnapshots"]
            if (type(parameters) is not dict or set(parameters) != set(_DOMAINS)
                    or type(baseline_snapshots) is not dict
                    or set(baseline_snapshots) != set(_DOMAINS)
                    or type(candidate_snapshots) is not dict
                    or set(candidate_snapshots) != set(_DOMAINS)):
                raise _invalid()
            for domain, profile_id in (("tax.policy", "tax-policy-v1"),
                                       ("tax.law", "tax-law-v1")):
                param = parameters[domain]
                if (type(param) is not dict or set(param) != _PROFILE_PARAMETER_KEYS
                        or param["profileId"] != profile_id
                        or param["profileVersion"] != "tax-knowledge-search-v1"
                        or param["readPolicyVersion"] != "tax-public-authenticated-v1"
                        or not _valid_hash(param["configSha256"])
                        or type(param["baselineMappingVersion"]) is not str
                        or not param["baselineMappingVersion"]
                        or param["candidateMappingVersion"] != declared_candidate["mappingVersion"]
                        or baseline_snapshots[domain] != _profile_snapshot(profile_id,
                            source_binding.index_name, source_binding.index_uuid,
                            param["profileVersion"], param["baselineMappingVersion"])
                        or candidate_snapshots[domain] != _profile_snapshot(profile_id,
                            candidate_binding.index_name, candidate_binding.index_uuid,
                            param["profileVersion"], param["candidateMappingVersion"])
                        or baseline_snapshots[domain] == candidate_snapshots[domain]):
                    raise _invalid()
            snapshots = {"baseline": baseline_snapshots, "candidate": candidate_snapshots}
            frozen_snapshots = tuple((arm, tuple((domain, snapshots[arm][domain])
                for domain in _DOMAINS)) for arm in _ARMS)
            model = value["modelBindings"]
            source_evidence = value["sourceBuildEvidence"]
            if (type(model) is not dict or set(model) != _MODEL_BINDING_KEYS
                    or any(not _valid_hash(model[key]) for key in (
                        "baselineModelSnapshotSha256", "currentModelSnapshotSha256",
                        "tokenizerSha256"))
                    or model["baselineRepresentationVersion"] != "policy-title-section-body-v1"
                    or model["candidateRepresentationVersion"] != "body-only-v2"
                    or type(source_evidence) is not dict
                    or set(source_evidence) != {"bindingPath", "bindingSha256",
                                                    "resultPath", "resultSha256"}
                    or source_evidence["bindingPath"]
                    != f"{_SOURCE_BUILD_DIRECTORY}/binding.json"
                    or source_evidence["resultPath"]
                    != f"{_SOURCE_BUILD_DIRECTORY}/result.json"
                    or not _valid_hash(source_evidence["bindingSha256"])
                    or not _valid_hash(source_evidence["resultSha256"])):
                raise _invalid()
            rows = value["representationBindings"]
            if (type(rows) is not list or not 1 <= len(rows) <= min(2000, source_binding.record_count)
                    or any(type(row) is not dict or set(row) != _REPRESENTATION_ROW_KEYS
                           for row in rows)):
                raise _invalid()
            pages = (source_binding.record_count + 249) // 250
            batches = (len(rows) + 31) // 32
            budget = {"esHttp": 42 + 4 * pages + 3 * batches,
                "embeddingHttp": batches, "writeOps": len(rows),
                "paid": 0, "retry": 0, "resume": 0,
                "onlineAliasWrites": 0, "candidates": 1}
            if (value["builderBudget"] != budget
                    or budget["esHttp"] > 400
                    or value["mappingScanBudget"] != {
                        "sourceEsHttp": 1 + pages, "candidateEsHttp": 1 + pages,
                        "retry": 0, "resume": 0}
                    or not _valid_comparison_budget(value["comparisonBudget"])
                    or any(type(final[key]) is not str or not _valid_hash(final[key])
                           for key in _FINAL_KEYS - {"schemaVersion", "kind",
                               "candidateIdentity", "candidateProfileSnapshots"})):
                raise _invalid()
            if len(plans) != 10:
                raise _invalid()
            cases: list[ComparisonCase] = []
            for row in value["cases"]:
                if (type(row) is not dict or set(row) != {"caseId", "question", "queryMode",
                        "selectedDomainIds", "necessarySources", "core", "retained", "plan", "planHash"}
                        or type(row["caseId"]) is not str or row["caseId"] not in plans
                        or type(row["question"]) is not str or not row["question"]
                        or type(row["queryMode"]) is not str
                        or type(row["selectedDomainIds"]) is not list
                        or any(type(domain) is not str for domain in row["selectedDomainIds"])
                        or type(row["necessarySources"]) is not list
                        or type(row["plan"]) is not dict
                        or type(row["core"]) is not bool or type(row["retained"]) is not bool
                        or type(row["planHash"]) is not str or _SHA.fullmatch(row["planHash"]) is None):
                    raise _invalid()
                plan = plans[row["caseId"]]
                original = frozen_cases[row["caseId"]]
                necessary = []
                for source_id in original["necessarySources"]:
                    source = source_by_id[source_id]
                    necessary.append({"documentId": source["documentId"],
                                      "chunkId": source["chunkId"],
                                      "contentSha256": source["contentSha256"]})
                if (type(plan) is not MinimalKnowledgeRetrievalPlan
                        or row["caseId"] != _RETRIEVAL_CASE_IDS[len(cases)]
                        or original["retrievalDenominator"] is not True
                        or row["question"] != original["question"]
                        or row["queryMode"] != original["queryMode"]
                        or row["selectedDomainIds"] != original["expectedDomains"]
                        or row["necessarySources"] != necessary
                        or row["core"] != (row["caseId"] in core_ids)
                        or row["retained"] is not True
                        or plan.original_question != row["question"]
                        or plan.query_mode.value != row["queryMode"]
                        or list(plan.selected_domain_ids) != row["selectedDomainIds"]
                        or plan_payload(plan) != row["plan"]
                        or plan_fingerprint(plan) != row["planHash"]):
                    raise _invalid()
                refs: list[CandidateRef] = []
                for source in row["necessarySources"]:
                    if type(source) is not dict or set(source) != {
                            "documentId", "chunkId", "contentSha256"}:
                        raise _invalid()
                    refs.append(CandidateRef(source["documentId"], source["chunkId"],
                                             source["contentSha256"]))
                cases.append(ComparisonCase(row["caseId"], plan, tuple(refs),
                                            row["core"], row["retained"]))
            if set(plans) != {case.case_id for case in cases}:
                raise _invalid()
            if (sum(len(case.plan.items) for case in cases) * 2
                    != _COMPARISON_BUDGET_FIXED["typedSearch"]
                    or sum(len(case.plan.selected_domain_ids) for case in cases) * 2
                    != _COMPARISON_BUDGET_FIXED["rerank"]):
                raise _invalid()
            return cls(tuple(cases), frozen_snapshots, value["uatFixtureSha256"],
                       expected_intent_sha256, expected_sha256, source_binding,
                       candidate_binding, intent_raw, raw)
        except (UnicodeError, json.JSONDecodeError, IndexError, KeyError, TypeError, ValueError):
            raise _invalid() from None


def comparison_spec_fingerprint(spec: ComparisonSpec) -> str:
    """Bind scored gold and plan data, even if a caller reuses an old hash string."""
    if type(spec) is not ComparisonSpec:
        raise _invalid()
    source = spec.source_corpus
    candidate = spec.candidate_corpus
    return hashlib.sha256(_canonical_bytes({
        "assessmentIntentSha256": spec.assessment_intent_sha256,
        "assessmentSha256": spec.assessment_sha256,
        "uatFixtureSha256": spec.uat_fixture_sha256,
        "profileSnapshots": {arm: dict(entries) for arm, entries in spec.profile_snapshots},
        "sourceCorpus": {"indexName": source.index_name, "indexUuid": source.index_uuid,
            "recordCount": source.record_count, "mappingSha256": source.mapping_sha256,
            "fullFingerprint": source.full_fingerprint},
        "candidateCorpus": {"indexName": candidate.index_name, "indexUuid": candidate.index_uuid,
            "recordCount": candidate.record_count, "mappingSha256": candidate.mapping_sha256,
            "fullFingerprint": candidate.full_fingerprint},
        "cases": [{"caseId": case.case_id, "planHash": plan_fingerprint(case.plan),
            "core": case.core, "retained": case.retained,
            "necessarySources": [{"documentId": ref.document_id, "chunkId": ref.chunk_id,
                                  "contentSha256": ref.content_sha256}
                                 for ref in case.necessary_sources]}
            for case in spec.cases],
    })).hexdigest()


@dataclass(frozen=True, slots=True)
class SourceId:
    es_id: str
    document_id: str
    chunk_id: str
    content_sha256: str

    def __post_init__(self) -> None:
        if (type(self.es_id) is not str or _SAFE_ID.fullmatch(self.es_id) is None
                or type(self.document_id) is not str or _SAFE_ID.fullmatch(self.document_id) is None
                or type(self.chunk_id) is not str or _SAFE_ID.fullmatch(self.chunk_id) is None
                or type(self.content_sha256) is not str or _SHA.fullmatch(self.content_sha256) is None):
            raise _invalid()


def _unique_json(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _invalid()
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise _invalid()


@dataclass(frozen=True, slots=True)
class FrozenIdMapping:
    """Strict, complete source-scan map; the typed API itself does not return ES _id."""

    index_name: str
    index_uuid: str
    source_fingerprint: str
    records: tuple[SourceId, ...] = field(repr=False)
    sha256: str

    def __post_init__(self) -> None:
        if (type(self.index_name) is not str or _SAFE_ID.fullmatch(self.index_name) is None
                or type(self.index_uuid) is not str or _SAFE_ID.fullmatch(self.index_uuid) is None
                or type(self.source_fingerprint) is not str or _SHA.fullmatch(self.source_fingerprint) is None
                or type(self.records) is not tuple or not 1 <= len(self.records) <= 22000
                or any(type(item) is not SourceId for item in self.records)
                or type(self.sha256) is not str or _SHA.fullmatch(self.sha256) is None):
            raise _invalid()
        ids = tuple(item.es_id for item in self.records)
        if (ids != tuple(sorted(ids)) or len(set(ids)) != len(ids)
                or len({(item.document_id, item.chunk_id) for item in self.records}) != len(self.records)):
            raise _invalid()
        canonical = {
            "schemaVersion": 1, "indexName": self.index_name, "indexUuid": self.index_uuid,
            "sourceFingerprint": self.source_fingerprint, "recordCount": len(self.records),
            "records": [{"id": item.es_id, "documentId": item.document_id,
                         "chunkId": item.chunk_id, "contentSha256": item.content_sha256}
                        for item in self.records],
        }
        raw = _canonical_bytes(canonical)
        if hashlib.sha256(raw).hexdigest() != self.sha256:
            raise _invalid()

    @classmethod
    def from_bytes(cls, raw: bytes, *, expected_sha256: str) -> FrozenIdMapping:
        if (type(raw) is not bytes or not 0 < len(raw) <= 16 * 1024 * 1024
                or type(expected_sha256) is not str
                or _SHA.fullmatch(expected_sha256) is None
                or hashlib.sha256(raw).hexdigest() != expected_sha256):
            raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ())
        try:
            value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json,
                parse_constant=_reject_constant)
            if (type(value) is not dict or set(value) != {"schemaVersion", "indexName", "indexUuid",
                    "sourceFingerprint", "recordCount", "records"}
                    or type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1
                    or type(value["indexName"]) is not str or _SAFE_ID.fullmatch(value["indexName"]) is None
                    or type(value["indexUuid"]) is not str or _SAFE_ID.fullmatch(value["indexUuid"]) is None
                    or type(value["sourceFingerprint"]) is not str
                    or _SHA.fullmatch(value["sourceFingerprint"]) is None
                    or type(value["recordCount"]) is not int
                    or not 1 <= value["recordCount"] <= 22000
                    or type(value["records"]) is not list
                    or len(value["records"]) != value["recordCount"]):
                raise _invalid()
            if raw != _canonical_bytes(value):
                raise _invalid()
            records: list[SourceId] = []
            for item in value["records"]:
                if type(item) is not dict or set(item) != {"id", "documentId", "chunkId", "contentSha256"}:
                    raise _invalid()
                records.append(SourceId(item["id"], item["documentId"], item["chunkId"],
                                        item["contentSha256"]))
            return cls(value["indexName"], value["indexUuid"], value["sourceFingerprint"],
                       tuple(records), expected_sha256)
        except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ()) from None

@dataclass(frozen=True, slots=True)
class ArmEndpoint:
    search: KnowledgeSearchPort = field(repr=False)
    # Profile snapshots differ from the physical full-source fingerprint.
    snapshots: tuple[tuple[str, str], ...]
    id_mapping: FrozenIdMapping = field(repr=False)


@dataclass(frozen=True, slots=True)
class StageRanks:
    domain_id: str
    path: str
    ranked: tuple[CandidateRef, ...]


@dataclass(frozen=True, slots=True)
class ArmTrace:
    arm: str
    keyword: tuple[StageRanks, ...]
    keyword_es_ids: tuple[tuple[str, tuple[str, ...]], ...]
    vector: tuple[StageRanks, ...]
    fused: tuple[CandidateRef, ...]
    reranked: tuple[StageRanks, ...]
    final20: tuple[CandidateRef, ...]
    read_policy_by_domain: tuple[tuple[str, str], ...]
    latency_seconds: float


@dataclass(frozen=True, slots=True)
class CaseTrace:
    case_id: str
    baseline: ArmTrace
    candidate: ArmTrace


@dataclass(frozen=True, slots=True)
class CallTotals:
    typed_search: int
    query_embedding: int
    online_rerank: int


@dataclass(frozen=True, slots=True)
class ComparisonRun:
    cases: tuple[CaseTrace, ...]
    calls: CallTotals
    assessment_sha256: str
    uat_fixture_sha256: str
    provenance_sha256: str
    comparison_spec_sha256: str
    evidence_kind: str


class ComparisonRunError(Exception):
    """Safe terminal reason and limited completed trace for append-only failure evidence."""

    def __init__(self, reason: str, calls: CallTotals, completed: tuple[CaseTrace, ...], *,
                 case_id: str | None = None, arm: str | None = None,
                 stage: str = "preflight", unexecuted_case_ids: tuple[str, ...] = ()) -> None:
        super().__init__(reason)
        self.reason = reason
        self.outcome = ("not_assessed" if reason in (
            "source_id_mapping_confounded", "runtime_provenance_missing") else "invalid_run")
        self.calls = calls
        self.completed = completed
        self.case_id = case_id
        self.arm = arm
        self.stage = stage
        self.unexecuted_case_ids = unexecuted_case_ids


class _Counts:
    def __init__(self) -> None:
        self.typed = 0
        self.embed = 0
        self.rerank = 0

    def snapshot(self) -> CallTotals:
        return CallTotals(self.typed, self.embed, self.rerank)


class _CachedEmbedding:
    def __init__(self, *, question: str, vector: tuple[float, ...]) -> None:
        self.question = question
        self.vector = vector
        self.calls = 0

    async def embed(self, *, text: str, timeout_s: float) -> tuple[float, ...]:
        if text != self.question or self.calls or timeout_s <= 0:
            raise _invalid()
        self.calls += 1
        return self.vector


class _TracingSearch:
    def __init__(self, *, delegate: KnowledgeSearchPort, plan: MinimalKnowledgeRetrievalPlan,
                 counts: _Counts, clock: Callable[[], float], endpoint: ArmEndpoint) -> None:
        self.delegate = delegate
        self.expected = {(item.logical_domain_id, item.path) for item in plan.items}
        self.snapshots = dict(endpoint.snapshots)
        self.id_map = {(item.document_id, item.chunk_id): item
                       for item in endpoint.id_mapping.records}
        self.counts = counts
        self.clock = clock
        self.started: float | None = None
        self.results: dict[tuple[str, RetrievalPath], PathRetrievalResult] = {}

    async def search(self, *, request: KnowledgePathRequest, context: KnowledgeRetrievalContext,
                     timeout_s: float) -> PathRetrievalResult:
        key = (request.logical_domain_id, request.path)
        if key not in self.expected or key in self.results or self.counts.typed >= MAX_TYPED:
            raise ComparisonRunError("typed_budget_or_plan_invalid", self.counts.snapshot(), ())
        self.counts.typed += 1  # An attempted call consumes budget even if it fails.
        if self.started is None:
            self.started = self.clock()
        result = await self.delegate.search(request=request, context=context, timeout_s=timeout_s)
        if result.kind in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT):
            if result.index_snapshot_id != self.snapshots[request.logical_domain_id]:
                raise ComparisonRunError("source_id_mapping_confounded", self.counts.snapshot(), ())
            for item in result.candidates:
                source = self.id_map.get((item.document_id, item.chunk_id))
                if source is None or source.content_sha256 != item.content_sha256:
                    raise ComparisonRunError("source_id_mapping_confounded", self.counts.snapshot(), ())
        self.results[key] = result
        return result


class _TracingRerank:
    def __init__(self, delegate: RerankPort, counts: _Counts) -> None:
        self.delegate = delegate
        self.counts = counts
        self.calls: list[tuple[tuple[AuthorizedKnowledgeCandidate, ...], tuple[RerankScore, ...]]] = []

    async def rerank(self, *, query: str, candidates: tuple[AuthorizedKnowledgeCandidate, ...],
                     timeout_s: float) -> tuple[RerankScore, ...]:
        if self.counts.rerank >= MAX_RERANK:
            raise ComparisonRunError("rerank_budget_exceeded", self.counts.snapshot(), ())
        self.counts.rerank += 1
        scores = await self.delegate.rerank(query=query, candidates=candidates, timeout_s=timeout_s)
        self.calls.append((candidates, scores))
        return scores


_PROVENANCE_FILES = ("scanPlan", "binding", "builderResult", "sourceScanResult",
                     "candidateScanResult")
_REPRESENTATION_ROW_KEYS = frozenset({
    "identifier", "document_id", "parent_document_id", "asset_id", "asset_version",
    "version", "input_sha256", "body_sha256",
})
_BUILD_BUDGET_KEYS = frozenset({
    "esHttp", "embeddingHttp", "writeOps", "paid", "retry", "resume",
    "onlineAliasWrites", "candidates",
})
_CANDIDATE_INPUT_KEYS = frozenset({
    "source_index", "source_uuid", "source_mapping_sha256", "source_fingerprint",
    "source_count", "read_alias", "online_index", "online_uuid",
    "online_mapping_sha256", "alias_snapshot_sha256", "candidate_index",
    "target_mapping_version", "target_mapping_sha256", "baseline_model_snapshot",
    "model_snapshot", "tokenizer_sha256", "baseline_representation_version",
})


def _sidecar(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise _invalid()
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json,
                       parse_constant=_reject_constant)
    if type(value) is not dict or raw != _canonical_bytes(value):
        raise _invalid()
    return value


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _valid_hash(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _verify_frozen_request_hashes(plan: dict[str, object], binding: dict[str, object],
                                  builder_spec: dict[str, object]) -> None:
    """Reconstruct both pre-ES freeze inputs from the sealed binding."""
    preliminary = {
        "schemaVersion": 2, "runId": binding["runId"],
        "frozenHead": binding["frozenHead"],
        "assessmentIntentSha256": binding["assessmentIntentSha256"],
        "candidate": {key: builder_spec[key] for key in _CANDIDATE_INPUT_KEYS},
        "representationBindings": binding["representationBindings"],
        "budget": binding["budget"],
        "mappingScanBudget": binding["mappingScanBudget"],
    }
    if (plan["requestCoreSha256"] != _sha256(_canonical_bytes(preliminary))
            or binding["freezeInputSha256"] != _sha256(_canonical_bytes({
                **preliminary, "idMappingSha256": binding["idMappingSha256"]}))):
        raise _invalid()


def _verify_representation_binding(binding: dict[str, object], builder_spec: dict[str, object],
                                   source_map: FrozenIdMapping, source_count: int) -> int:
    rows = binding["representationBindings"]
    if (type(rows) is not list or not 1 <= len(rows) <= min(2000, source_count)
            or builder_spec["mode"] != "representation"
            or builder_spec["baseline_representation_version"] != "policy-title-section-body-v1"
            or builder_spec["representation_version"] != "body-only-v2"
            or builder_spec["changes"] != []
            or type(builder_spec["update_ids"]) is not list
            or type(builder_spec["representation_scope"]) is not list
            or not _valid_hash(builder_spec["tokenizer_sha256"])
            or type(builder_spec["workspace"]) is not str
            or not builder_spec["workspace"]):
        raise _invalid()
    source_by_id = {record.es_id: record for record in source_map.records}
    expected_scope: list[dict[str, str]] = []
    bindings: list[list[str]] = []
    ids: list[str] = []
    for row in rows:
        if (type(row) is not dict or set(row) != _REPRESENTATION_ROW_KEYS
                or any(type(value) is not str for value in row.values())
                or any(not value or len(value) > 256 for value in row.values())
                or row["version"] != "body-only-v2"
                or any(not _valid_hash(row[key]) for key in (
                    "asset_version", "input_sha256", "body_sha256"))
                or row["input_sha256"] != row["body_sha256"]):
            raise _invalid()
        source = source_by_id.get(row["identifier"])
        if (source is None or source.document_id != row["document_id"]
                or source.content_sha256 != row["body_sha256"]):
            raise _invalid()
        ids.append(row["identifier"])
        bindings.append([row["identifier"], row["version"], row["input_sha256"],
                         row["body_sha256"]])
        expected_scope.append({key: row[key] for key in (
            "identifier", "document_id", "parent_document_id", "asset_id", "asset_version")})
    if (len(set(ids)) != len(ids)
            or len({row["parent_document_id"] for row in rows}) > 30
            or builder_spec["update_ids"] != ids
            or builder_spec["representation_scope"] != expected_scope
            or builder_spec["representation_binding_sha256"] != _sha256(_canonical_bytes(bindings))):
        raise _invalid()
    for name in ("baseline_model_snapshot", "model_snapshot"):
        snapshot = builder_spec[name]
        if (type(snapshot) is not dict or set(snapshot) != {"container", "model"}
                or type(snapshot["container"]) is not dict
                or type(snapshot["model"]) is not dict
                or set(snapshot["container"]) != {
                    "id", "image", "started", "running", "path", "args", "ports"}
                or set(snapshot["model"]) != {
                    "revision", "files", "service", "implementation", "max_length",
                    "packages", "cache_provenance"}
                or builder_spec[f"{name}_sha256"] != _sha256(_canonical_bytes(snapshot))):
            raise _invalid()
    baseline_model = builder_spec["baseline_model_snapshot"]
    current_model = builder_spec["model_snapshot"]
    if type(baseline_model) is not dict or type(current_model) is not dict:
        raise _invalid()
    baseline_container = baseline_model["container"]
    current_container = current_model["container"]
    if type(baseline_container) is not dict or type(current_container) is not dict:
        raise _invalid()
    if (baseline_model["model"] != current_model["model"]
            or {key: value for key, value in baseline_container.items()
                if key != "started"}
            != {key: value for key, value in current_container.items()
                if key != "started"}):
        raise _invalid()
    return len(ids)


def _verify_provenance(spec: ComparisonSpec, baseline: ArmEndpoint,
                       candidate: ArmEndpoint, sidecars: Mapping[str, bytes]) -> str:
    """Cross-check read-only scan evidence, builder binding and both full-source maps."""
    try:
        if not isinstance(sidecars, Mapping) or set(sidecars) != set(_PROVENANCE_FILES):
            raise _invalid()
        values = {name: _sidecar(sidecars[name]) for name in _PROVENANCE_FILES}
        plan = values["scanPlan"]
        binding = values["binding"]
        built = values["builderResult"]
        source_scan = values["sourceScanResult"]
        candidate_scan = values["candidateScanResult"]
        intent = _sidecar(spec.intent_raw)
        final = _sidecar(spec.final_raw)
        profiles = cast(dict[str, dict[str, object]], intent["profileParameters"])
        source = spec.source_corpus
        frozen_candidate = spec.candidate_corpus
        source_map = baseline.id_mapping
        candidate_map = candidate.id_mapping
        builder_spec = binding["spec"]
        budget = plan["mappingScanBudget"]
        if (type(builder_spec) is not dict or type(budget) is not dict
                or type(plan.get("schemaVersion")) is not int or plan["schemaVersion"] != 2
                or plan["kind"] != "knowledge_b_mapping_scan_plan_v2"
                or type(binding.get("schemaVersion")) is not int or binding["schemaVersion"] != 2
                or binding["kind"] != "knowledge_b_representation_candidate_v2"
                or type(built.get("schemaVersion")) is not int or built["schemaVersion"] != 2
                or binding["sourceVerification"] != "pending_builder_live_preflight"
                or plan["branch"] != binding["branch"] or plan["branch"] != "codex_0915"
                or type(plan["frozenHead"]) is not str
                or re.fullmatch(r"[0-9a-f]{40}", plan["frozenHead"]) is None
                or plan["fixtureGitBlobSha256"] != spec.uat_fixture_sha256
                or not _valid_hash(plan["requestCoreSha256"])
                or not _valid_hash(binding["freezeInputSha256"])
                or binding["scanPlanSha256"] != _sha256(sidecars["scanPlan"])
                or binding["sourceMapScanResultSha256"] != _sha256(sidecars["sourceScanResult"])
                or built["bindingSha256"] != _sha256(sidecars["binding"])
                or plan["assessmentIntentSha256"] != spec.assessment_intent_sha256
                or binding["assessmentIntentSha256"] != spec.assessment_intent_sha256
                or built["assessmentIntentSha256"] != spec.assessment_intent_sha256
                or builder_spec["assessment_intent_sha256"] != spec.assessment_intent_sha256
                or final["assessmentIntentSha256"] != spec.assessment_intent_sha256
                or final["bindingSha256"] != _sha256(sidecars["binding"])
                or final["builderResultSha256"] != _sha256(sidecars["builderResult"])
                or final["sourceMapScanResultSha256"] != _sha256(sidecars["sourceScanResult"])
                or final["candidateMapScanResultSha256"] != _sha256(sidecars["candidateScanResult"])
                or final["sourceIdMappingSha256"] != source_map.sha256
                or final["candidateIdMappingSha256"] != candidate_map.sha256
                or final["candidateIdentity"] != {
                    "indexName": frozen_candidate.index_name,
                    "indexUuid": frozen_candidate.index_uuid,
                    "mappingSha256": frozen_candidate.mapping_sha256,
                    "sourceFingerprint": frozen_candidate.full_fingerprint,
                    "recordCount": frozen_candidate.record_count}
                or final["candidateProfileSnapshots"] != dict(dict(spec.profile_snapshots)["candidate"])
                or plan["runId"] != binding["runId"] or built["runId"] != plan["runId"]
                or plan["frozenHead"] != binding["frozenHead"]
                or plan["sourceIndex"] != source.index_name
                or plan["sourceUuid"] != source.index_uuid
                or plan["sourceCount"] != source.record_count
                or plan["sourceMappingSha256"] != source.mapping_sha256
                or plan["sourceFingerprint"] != source.full_fingerprint
                or builder_spec["source_index"] != source.index_name
                or builder_spec["source_uuid"] != source.index_uuid
                or builder_spec["source_count"] != source.record_count
                or builder_spec["source_mapping_sha256"] != source.mapping_sha256
                or builder_spec["source_fingerprint"] != source.full_fingerprint
                or builder_spec["candidate_index"] != plan["candidateIndex"]
                or builder_spec["target_mapping_sha256"] != plan["candidateMappingSha256"]
                or binding["idMappingSha256"] != source_map.sha256
                or binding["idMappingSourceFingerprint"] != source.full_fingerprint
                or intent["representationBindings"] != binding["representationBindings"]
                or intent["builderBudget"] != binding["budget"]
                or intent["mappingScanBudget"] != binding["mappingScanBudget"]
                or intent["source"] != {"indexName": source.index_name,
                    "indexUuid": source.index_uuid, "mappingSha256": source.mapping_sha256,
                    "sourceFingerprint": source.full_fingerprint,
                    "recordCount": source.record_count}
                or intent["candidate"] != {"indexName": frozen_candidate.index_name,
                    "mappingSha256": frozen_candidate.mapping_sha256,
                    "mappingVersion": builder_spec["target_mapping_version"]}
                or intent["modelBindings"] != {
                    "baselineModelSnapshotSha256": builder_spec["baseline_model_snapshot_sha256"],
                    "currentModelSnapshotSha256": builder_spec["model_snapshot_sha256"],
                    "tokenizerSha256": builder_spec["tokenizer_sha256"],
                    "baselineRepresentationVersion": builder_spec["baseline_representation_version"],
                    "candidateRepresentationVersion": builder_spec["representation_version"]}
                or not _valid_comparison_budget(intent["comparisonBudget"])
                or built["status"] != "built_read_only_unpublished"
                or built["sourceVerifiedByBuilder"] is not True
                or built["candidateMapping"] != "pending_postbuild_readonly_scan"
                or built["executionKind"] not in ("fake", "local")
                or any(type(built[key]) is not int or built[key] != 0 for key in (
                    "paid", "retry", "resume", "onlineAliasWrites"))
                or built["candidateIndex"] != plan["candidateIndex"]
                or built["candidateIndex"] != frozen_candidate.index_name
                or built["candidateUuid"] != frozen_candidate.index_uuid
                or built["candidateFingerprint"] != frozen_candidate.full_fingerprint
                or built["candidateCount"] != source.record_count
                or source_map.index_name != source.index_name
                or source_map.index_uuid != source.index_uuid
                or source_map.source_fingerprint != source.full_fingerprint
                or candidate_map.index_name != frozen_candidate.index_name
                or candidate_map.index_uuid != frozen_candidate.index_uuid
                or candidate_map.source_fingerprint != frozen_candidate.full_fingerprint
                or len(source_map.records) != source.record_count
                or len(candidate_map.records) != source.record_count):
            raise _invalid()
        per_arm = 1 + (source.record_count + 249) // 250
        if (budget != {"sourceEsHttp": per_arm, "candidateEsHttp": per_arm,
                       "retry": 0, "resume": 0}
                or binding["mappingScanBudget"] != budget):
            raise _invalid()
        _verify_frozen_request_hashes(plan, binding, builder_spec)
        updates = _verify_representation_binding(binding, builder_spec, source_map,
                                                  source.record_count)
        batches = (updates + 31) // 32
        expected_budget = {"esHttp": 42 + 4 * ((source.record_count + 249) // 250)
                           + 3 * batches,
                           "embeddingHttp": batches, "writeOps": updates,
                           "paid": 0, "retry": 0, "resume": 0,
                           "onlineAliasWrites": 0, "candidates": 1}
        if (type(binding["budget"]) is not dict
                or set(binding["budget"]) != _BUILD_BUDGET_KEYS
                or binding["budget"] != expected_budget
                or any(type(binding["budget"][key]) is not int for key in _BUILD_BUDGET_KEYS)
                or builder_spec["max_http_requests"] != expected_budget["esHttp"]
                or builder_spec["max_embedding_requests"] != batches
                or builder_spec["max_write_ops"] != updates
                or any(type(builder_spec[key]) is not int for key in (
                    "max_http_requests", "max_embedding_requests", "max_write_ops"))
                or type(built["updatedCount"]) is not int or built["updatedCount"] != updates
                or type(built["esHttp"]) is not int
                or not 1 <= built["esHttp"] <= expected_budget["esHttp"]
                or type(built["embeddingHttp"]) is not int
                or built["embeddingHttp"] != batches):
            raise _invalid()
        for arm, result, mapping in (("source", source_scan, source_map),
                                     ("candidate", candidate_scan, candidate_map)):
            version_key = "baselineMappingVersion" if arm == "source" else "candidateMappingVersion"
            if (type(result.get("schemaVersion")) is not int or result["schemaVersion"] != 2
                    or result["assessmentIntentSha256"] != spec.assessment_intent_sha256
                    or result["arm"] != arm or result["status"] != "scanned_read_only"
                    or result["reason"] is not None
                    or result["indexName"] != mapping.index_name
                    or result["indexUuid"] != mapping.index_uuid
                    or any(result["mappingVersion"] != profiles[domain][version_key]
                           for domain in _DOMAINS)
                    or result["sourceFingerprint"] != mapping.source_fingerprint
                    or result["sha256"] != mapping.sha256
                    or result["recordCount"] != source.record_count
                    or type(result["esHttp"]) is not int
                    or result["esHttp"] != per_arm
                    or result["maxEsHttp"] != per_arm
                    or type(result["retry"]) is not int or result["retry"] != 0
                    or type(result["resume"]) is not int or result["resume"] != 0):
                raise _invalid()
        # The existing five sidecars prove only the candidate build and full-source
        # scans. They cannot attest isolated Java process ownership, fixed physical
        # ES request paths, pre/post alias identity or real comparison call totals.
        # Until the separate runner supplies and verifies that evidence, local is
        # intentionally ineligible for any typed comparison or quality verdict.
        if built["executionKind"] == "local":
            raise ComparisonRunError("runtime_provenance_missing", CallTotals(0, 0, 0), ())
        return hashlib.sha256(_canonical_bytes({
            "assessmentIntentSha256": spec.assessment_intent_sha256,
            "assessmentSha256": spec.assessment_sha256,
            "uatFixtureSha256": spec.uat_fixture_sha256,
            "sidecarSha256": {name: hashlib.sha256(sidecars[name]).hexdigest()
                             for name in _PROVENANCE_FILES},
            "sourceIdMappingSha256": source_map.sha256,
            "candidateIdMappingSha256": candidate_map.sha256,
        })).hexdigest()
    except (UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ()) from None


def _validate_endpoints(spec: ComparisonSpec, baseline: ArmEndpoint, candidate: ArmEndpoint) -> None:
    for arm, endpoint in (("baseline", baseline), ("candidate", candidate)):
        if (type(endpoint) is not ArmEndpoint or type(endpoint.snapshots) is not tuple
                or endpoint.snapshots != dict(spec.profile_snapshots)[arm]
                or any(type(snapshot) is not str or _SHA.fullmatch(snapshot) is None
                       for _, snapshot in endpoint.snapshots)
                or type(endpoint.id_mapping) is not FrozenIdMapping):
            raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ())
    if (baseline.id_mapping.index_name == candidate.id_mapping.index_name
            or baseline.id_mapping.index_uuid == candidate.id_mapping.index_uuid
            or baseline.id_mapping.records != candidate.id_mapping.records):
        raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ())


def _trace(*, arm: str, case: ComparisonCase, endpoint: ArmEndpoint,
           search: _TracingSearch, rerank: _TracingRerank, final: tuple[CandidateRef, ...],
           finished: float) -> ArmTrace:
    if search.started is None or not math.isfinite(finished - search.started) or finished <= search.started:
        raise _invalid()
    sets: list[PathCandidateSet] = []
    keyword: list[StageRanks] = []
    keyword_ids: list[tuple[str, tuple[str, ...]]] = []
    vector: list[StageRanks] = []
    policies: list[tuple[str, str]] = []
    snapshots = dict(endpoint.snapshots)
    id_map = {(record.document_id, record.chunk_id): record
              for record in endpoint.id_mapping.records}
    for domain in case.plan.selected_domain_ids:
        domain_results = []
        for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
            result = search.results.get((domain, path))
            if result is None or result.kind not in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT):
                raise _invalid()
            if (result.index_snapshot_id != snapshots[domain]
                    or result.profile_version != "tax-knowledge-search-v1"
                    or not result.read_policy_version):
                raise _invalid()
            item = _candidate_set(result, limit=case.plan.settings.per_path_candidate_limit)
            sets.append(item)
            domain_results.append(item)
            ranked = StageRanks(domain, path.value, tuple(CandidateRef.from_candidate(c) for c in item.candidates))
            (keyword if path is RetrievalPath.KEYWORD else vector).append(ranked)
            ordered_ids = []
            for ref in ranked.ranked:
                source = id_map.get((ref.document_id, ref.chunk_id))
                if source is None or source.content_sha256 != ref.content_sha256:
                    raise ComparisonRunError("source_id_mapping_confounded", CallTotals(0, 0, 0), ())
                ordered_ids.append(source.es_id)
            if path is RetrievalPath.KEYWORD:
                keyword_ids.append((domain, tuple(ordered_ids)))
        if domain_results[0].read_policy_version != domain_results[1].read_policy_version:
            raise _invalid()
        policies.append((domain, domain_results[0].read_policy_version))
    if len(search.results) != len(case.plan.items):
        raise _invalid()
    all_sets = tuple(sets)
    fused = ReciprocalRankFusion().fuse(all_sets)
    queues = []
    reranked: list[StageRanks] = []
    score_index = 0
    for domain in case.plan.selected_domain_ids:
        pool = domain_pool(all_sets, domain)
        if not pool:
            continue
        if score_index >= len(rerank.calls):
            raise _invalid()
        candidates, scores = rerank.calls[score_index]
        score_index += 1
        if candidates != tuple(item.candidate for item in pool):
            raise _invalid()
        queue = order_domain(pool, scores)
        queues.append(queue)
        reranked.append(StageRanks(domain, "rerank", tuple(CandidateRef.from_candidate(item.candidate)
                                                          for item, _ in queue)))
    if score_index != len(rerank.calls):
        raise _invalid()
    recomputed = round_robin(tuple(queues), fused, limit=case.plan.settings.final_candidate_limit)
    if final != tuple(CandidateRef.from_candidate(item.candidate) for item in recomputed):
        raise _invalid()
    return ArmTrace(arm=arm, keyword=tuple(keyword), keyword_es_ids=tuple(keyword_ids), vector=tuple(vector),
        fused=tuple(CandidateRef.from_candidate(item.candidate) for item in fused),
        reranked=tuple(reranked), final20=final, read_policy_by_domain=tuple(policies),
        latency_seconds=finished - search.started)


async def run_comparison(*, spec: ComparisonSpec, baseline: ArmEndpoint, candidate: ArmEndpoint,
                         embedding: EmbeddingPort, rerank: RerankPort,
                         context_for: Callable[[str], KnowledgeRetrievalContext],
                         provenance_sidecars: Mapping[str, bytes],
                         clock: Callable[[], float] = time.perf_counter) -> ComparisonRun:
    """Diagnose frozen cases with injected fake ports; real admission remains closed."""
    if type(spec) is not ComparisonSpec:
        raise _invalid()
    try:
        _validate_endpoints(spec, baseline, candidate)
        provenance_sha256 = _verify_provenance(spec, baseline, candidate, provenance_sidecars)
    except ComparisonRunError as exc:
        raise ComparisonRunError(exc.reason, CallTotals(0, 0, 0), (),
            stage="preflight", unexecuted_case_ids=tuple(case.case_id for case in spec.cases)) from None
    counts = _Counts()
    completed: list[CaseTrace] = []
    current_case: str | None = None
    current_arm: str | None = None
    current_stage = "embedding"
    try:
        for case_number, case in enumerate(spec.cases):
            current_case = case.case_id
            current_arm = None
            current_stage = "embedding"
            if counts.embed >= MAX_EMBED:
                raise _invalid()
            counts.embed += 1
            vector = await embedding.embed(text=case.plan.original_question, timeout_s=5.0)
            if (type(vector) is not tuple or len(vector) != 1024
                    or any(type(value) is not float or not math.isfinite(value) for value in vector)):
                raise _invalid()
            context = context_for(case.case_id)
            if type(context) is not KnowledgeRetrievalContext or context.request_id != case.case_id:
                raise _invalid()
            traces: dict[str, ArmTrace] = {}
            ordered = _ARMS if case_number % 2 == 0 else tuple(reversed(_ARMS))
            for arm in ordered:
                current_arm = arm
                current_stage = "typed_retrieval_and_rerank"
                endpoint = baseline if arm == "baseline" else candidate
                # The same immutable context, token, ACL scope, deadline and cancellation
                # object are passed to both arms; no arm-specific context factory exists.
                cached = _CachedEmbedding(question=case.plan.original_question, vector=vector)
                search = _TracingSearch(delegate=endpoint.search, plan=case.plan, counts=counts,
                                        clock=clock, endpoint=endpoint)
                scored = _TracingRerank(delegate=rerank, counts=counts)
                result = await MinimalKnowledgeRetrievalStage(search=search, embedding=cached,
                    rerank=scored, settings=case.plan.settings).execute(plan=case.plan, context=context, timeout_s=20.0)
                finished = clock()
                if (result.kind not in (RetrievalStageKind.SUCCESS, RetrievalStageKind.NO_RESULT)
                        or result.coverage is None or not result.coverage.complete
                        or result.coverage.failed_paths or cached.calls != 1):
                    raise _invalid()
                batch = result.batch
                if result.kind is RetrievalStageKind.SUCCESS and batch is None:
                    raise _invalid()
                final = () if batch is None else tuple(CandidateRef.from_candidate(item.candidate)
                                                      for item in batch.candidates)
                traces[arm] = _trace(arm=arm, case=case, endpoint=endpoint,
                    search=search, rerank=scored, final=final, finished=finished)
            if traces["baseline"].read_policy_by_domain != traces["candidate"].read_policy_by_domain:
                raise _invalid()
            completed.append(CaseTrace(case.case_id, traces["baseline"], traces["candidate"]))
        return ComparisonRun(tuple(completed), counts.snapshot(), spec.assessment_sha256,
                             spec.uat_fixture_sha256, provenance_sha256,
                             comparison_spec_fingerprint(spec), "synthetic_only")
    except ComparisonRunError as exc:
        raise ComparisonRunError(exc.reason, counts.snapshot(), tuple(completed),
            case_id=current_case, arm=current_arm, stage=current_stage,
            unexecuted_case_ids=tuple(item.case_id for item in spec.cases[len(completed):])) from None
    except Exception:
        # Never serialize a raw adapter/provider exception or its response.
        raise ComparisonRunError("comparison_execution_failed", counts.snapshot(), tuple(completed),
            case_id=current_case, arm=current_arm, stage=current_stage,
            unexecuted_case_ids=tuple(item.case_id for item in spec.cases[len(completed):])) from None


BlindKey = tuple[str, str, str, str]


def blind_label_pool(run: ComparisonRun) -> tuple[BlindKey, ...]:
    """Sorted union for human labeling, with no arm identity or source body."""
    return tuple(sorted({(case.case_id, ref.document_id, ref.chunk_id, ref.content_sha256)
                         for case in run.cases for arm in (case.baseline, case.candidate)
                         for ref in arm.final20}))


@dataclass(frozen=True, slots=True)
class CaseMetrics:
    case_id: str
    baseline_recall: float
    candidate_recall: float
    baseline_precision: float | None
    candidate_precision: float | None
    stage_required_ranks: tuple[tuple[str, str, tuple[int | None, ...]], ...]


@dataclass(frozen=True, slots=True)
class ComparisonMetrics:
    outcome: str
    reasons: tuple[str, ...]
    macro_baseline_recall: float
    macro_candidate_recall: float
    macro_baseline_precision: float | None
    macro_candidate_precision: float | None
    median_baseline_latency: float
    median_candidate_latency: float
    case_metrics: tuple[CaseMetrics, ...]
    label_pool_size: int
    unjudged_count: int


def _ranked_stages(trace: ArmTrace) -> tuple[tuple[str, str, tuple[CandidateRef, ...]], ...]:
    return tuple((item.domain_id, item.path, item.ranked) for item in (*trace.keyword, *trace.vector,
                                                                      *trace.reranked)) + (
        ("all", "rrf", trace.fused), ("all", "final20", trace.final20),
    )


def score_comparison(*, spec: ComparisonSpec, run: ComparisonRun,
                     labels: Mapping[BlindKey, bool] | None) -> ComparisonMetrics:
    """Exact UAT_02 §6.1 scoring; missing blind labels never become false labels."""
    if (type(spec) is not ComparisonSpec or type(run) is not ComparisonRun
            or len(run.cases) != len(spec.cases)
            or run.assessment_sha256 != spec.assessment_sha256
            or run.uat_fixture_sha256 != spec.uat_fixture_sha256
            or type(run.provenance_sha256) is not str or _SHA.fullmatch(run.provenance_sha256) is None
            or run.comparison_spec_sha256 != comparison_spec_fingerprint(spec)
            or run.evidence_kind != "synthetic_only"
            or tuple(case.case_id for case in run.cases) != tuple(case.case_id for case in spec.cases)):
        raise _invalid()
    pool = blind_label_pool(run)
    judged: Mapping[BlindKey, bool] = {} if labels is None else labels
    if (not isinstance(judged, Mapping) or any(type(key) is not tuple or len(key) != 4
            or key not in pool or type(value) is not bool for key, value in judged.items())):
        raise _invalid()
    missing = len(pool) - len(judged)
    reasons: list[str] = []
    reasons.append("synthetic_only")
    if missing:
        reasons.append("blind_labels_missing")
    recalls: dict[str, list[float]] = {arm: [] for arm in _ARMS}
    precisions: dict[str, list[float]] = {arm: [] for arm in _ARMS}
    latencies: dict[str, list[float]] = {arm: [] for arm in _ARMS}
    case_metrics: list[CaseMetrics] = []
    for case, trace in zip(spec.cases, run.cases, strict=True):
        if trace.baseline.arm != "baseline" or trace.candidate.arm != "candidate":
            raise _invalid()
        stage_ranks: list[tuple[str, str, tuple[int | None, ...]]] = []
        case_recalls: dict[str, float] = {}
        case_precisions: dict[str, float | None] = {}
        for arm in _ARMS:
            arm_trace = trace.baseline if arm == "baseline" else trace.candidate
            if (not math.isfinite(arm_trace.latency_seconds) or arm_trace.latency_seconds <= 0
                    or len(arm_trace.final20) > 20 or len(set(arm_trace.final20)) != len(arm_trace.final20)):
                raise _invalid()
            final_set = set(arm_trace.final20)
            recall = sum(source in final_set for source in case.necessary_sources) / len(case.necessary_sources)
            case_recalls[arm] = recall
            recalls[arm].append(recall)
            latencies[arm].append(arm_trace.latency_seconds)
            for domain, stage, ranked in _ranked_stages(arm_trace):
                stage_ranks.append((f"{arm}:{domain}", stage, tuple(
                    ranked.index(source) + 1 if source in ranked else None for source in case.necessary_sources)))
            precision = None if missing else (sum(judged[(case.case_id, ref.document_id, ref.chunk_id,
                ref.content_sha256)] for ref in arm_trace.final20) / len(arm_trace.final20)
                if arm_trace.final20 else 0.0)
            case_precisions[arm] = precision
            if precision is not None:
                precisions[arm].append(precision)
        if (case.core or case.retained) and case_recalls["candidate"] < case_recalls["baseline"]:
            reasons.append(f"coverage_regression:{case.case_id}")
        for domain in case.plan.selected_domain_ids:
            base_ids = dict(trace.baseline.keyword_es_ids).get(domain)
            candidate_ids = dict(trace.candidate.keyword_es_ids).get(domain)
            if base_ids is None or candidate_ids is None:
                raise _invalid()
            if base_ids != candidate_ids:
                reasons.append(f"keyword_order_confounded:{case.case_id}:{domain}")
            if domain == "tax.law":
                for stage in ("vector", "reranked"):
                    base_items = getattr(trace.baseline, stage)
                    cand_items = getattr(trace.candidate, stage)
                    left = next(item.ranked for item in base_items if item.domain_id == domain)
                    right = next(item.ranked for item in cand_items if item.domain_id == domain)
                    if left != right:
                        reasons.append(f"unchanged_domain_confounded:{case.case_id}:{stage}")
        case_metrics.append(CaseMetrics(case.case_id, case_recalls["baseline"], case_recalls["candidate"],
            case_precisions["baseline"], case_precisions["candidate"], tuple(stage_ranks)))
    baseline_recall = statistics.mean(recalls["baseline"])
    candidate_recall = statistics.mean(recalls["candidate"])
    baseline_precision = statistics.mean(precisions["baseline"]) if not missing else None
    candidate_precision = statistics.mean(precisions["candidate"]) if not missing else None
    baseline_latency = statistics.median(latencies["baseline"])
    candidate_latency = statistics.median(latencies["candidate"])
    if candidate_recall <= baseline_recall:
        reasons.append("recall_not_improved")
    if not missing and candidate_precision is not None and baseline_precision is not None \
            and candidate_precision < baseline_precision:
        reasons.append("precision_regression")
    if candidate_latency > baseline_latency * 1.10:
        reasons.append("latency_regression")
    # A fake-only run may diagnose ranking, but never certifies actual B quality.
    outcome = "not_assessed"
    return ComparisonMetrics(outcome, tuple(reasons), baseline_recall, candidate_recall,
        baseline_precision, candidate_precision, baseline_latency, candidate_latency,
        tuple(case_metrics), len(pool), missing)
