"""Strict, offline-only question/source fixture; no gold enters a retrieval plan."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from agent_runtime.knowledge.contracts import KnowledgeEvidenceRequirement, KnowledgeRequirementKind
from agent_runtime.knowledge.evidence_requirements import valid_plan_text, validate_evidence_requirements, validate_requirement_focuses
from agent_runtime.knowledge.contracts import KnowledgeQuestionKind
from agent_runtime.knowledge.question_semantics import QuestionSemanticGuard
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.contracts import QuestionEgressDisposition

PATH = Path(__file__).with_name("retrieval_benchmark.v1.json")
DOMAINS = {"tax.policy", "tax.law"}
ERROR = "benchmark_fixture_invalid"


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    chunk_id: str
    sha256: str
    domain_id: str
    family: str
    anchors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    split: str
    question: str
    domains: tuple[str, ...]
    requirements: tuple[KnowledgeEvidenceRequirement, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Dataset:
    sha256: str
    binding_sha256: str
    sources: tuple[Source, ...]
    cases: tuple[Case, ...]

    @property
    def limits(self) -> dict[str, int]:
        return {"search": sum(2 * len(c.domains) for c in self.cases),
                "embedding": sum(len(c.domains) for c in self.cases),
                "rerank": sum(len(c.requirements) for c in self.cases)}

    def probe_inputs(self) -> dict[str, Any]:
        # Only question/domains/requirements go into SPECIFICATIONS. Sources are
        # separate evaluator inputs, never used to derive a focus or query.
        return {
            "CASES": tuple({"caseId": c.id, "question": c.question,
                            "requiredGold": c.sources, "reason": None} for c in self.cases),
            "GOLD": {s.id: {"chunk": s.chunk_id, "sha256": s.sha256, "clause": s.anchors[0]} for s in self.sources},
            "SPECIFICATIONS": tuple((c.id, "lookup", tuple((d, c.question) for d in c.domains),
                                     tuple((r.domain_id, r.kind.value, r.focus) for r in c.requirements)) for c in self.cases),
            "LIMITS": self.limits,
        }


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(ERROR)
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise ValueError(ERROR)


def _obj(value: object, keys: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != set(keys.split()):
        raise ValueError(ERROR)
    return value


def _seq(value: object, low: int, high: int) -> list[Any]:
    if type(value) is not list or not low <= len(value) <= high:
        raise ValueError(ERROR)
    return value


def _text(value: object, pattern: str | None = None) -> str:
    if not valid_plan_text(value, max_chars=256) or type(value) is not str:
        raise ValueError(ERROR)
    if pattern is not None and re.fullmatch(pattern, value) is None:
        raise ValueError(ERROR)
    return value


def load_dataset(raw: bytes | None = None) -> Dataset:
    if raw is None:
        with PATH.open("rb") as stream:
            raw = stream.read(131073)
    if type(raw) is not bytes or not 1 <= len(raw) <= 131072:
        raise ValueError(ERROR)
    root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant),
                "schemaVersion datasetId bindingSha256 sourceReview limitations sources cases")
    if (type(root["schemaVersion"]) is not int or root["schemaVersion"] != 1
            or root["datasetId"] != "retrieval-benchmark-v1"
            or root["sourceReview"] != "executor_source_inspection_not_external_human_approval"
            or root["limitations"] != ["present_sources_only", "manual_domains_not_llm_rewrite", "no_summary",
                                       "ungraded_relevance", "holdout_for_this_tuning_round_only"]):
        raise ValueError(ERROR)
    sources = []
    for item in _seq(root["sources"], 20, 20):
        s = _obj(item, "id chunkId sha256 domainId family anchors")
        anchors = tuple(_text(a) for a in _seq(s["anchors"], 1, 4))
        source = Source(_text(s["id"], r"[a-z0-9_]{1,48}"),
                        _text(s["chunkId"], r"[A-Za-z0-9._#-]{1,256}"),
                        _text(s["sha256"], r"[0-9a-f]{64}"), _text(s["domainId"]),
                        _text(s["family"], r"[a-z_]{1,48}"), anchors)
        if source.domain_id not in DOMAINS or len(set(anchors)) != len(anchors):
            raise ValueError(ERROR)
        sources.append(source)
    by_id = {s.id: s for s in sources}
    if len(by_id) != len(sources) or len({s.chunk_id for s in sources}) != len(sources):
        raise ValueError(ERROR)
    cases = []
    families: dict[str, set[str]] = {"development": set(), "holdout": set()}
    for ordinal, item in enumerate(_seq(root["cases"], 24, 24), 1):
        c = _obj(item, "caseId split corpusState question domains requirements requiredSources")
        domains = tuple(_text(d) for d in _seq(c["domains"], 1, 2))
        refs = tuple(_text(s) for s in _seq(c["requiredSources"], 1, 8))
        split = _text(c["split"])
        if (c["caseId"] != f"KRB-{ordinal:03d}" or c["corpusState"] != "present"
                or split != ("development" if ordinal <= 16 else "holdout")
                or len(set(domains)) != len(domains) or not set(domains) <= DOMAINS
                or len(set(refs)) != len(refs) or not set(refs) <= set(by_id)
                or {by_id[s].domain_id for s in refs} != set(domains)):
            raise ValueError(ERROR)
        requirements = []
        for i, item in enumerate(_seq(c["requirements"], 1, 4), 1):
            r = _obj(item, "domainId kind focus")
            requirements.append(KnowledgeEvidenceRequirement(requirement_id=f"r{i}",
                domain_id=_text(r["domainId"]), kind=KnowledgeRequirementKind(_text(r["kind"])), focus=_text(r["focus"])))
        question = _text(c["question"])
        validate_evidence_requirements(question_kind=KnowledgeQuestionKind.LOOKUP,
                                      requirements=tuple(requirements), domain_ids=domains)
        validate_requirement_focuses(original_question=question, requirements=tuple(requirements),
                                     semantic_guard=QuestionSemanticGuard())
        if QuestionEgressGuard().evaluate(question).disposition is not QuestionEgressDisposition.ALLOWED:
            raise ValueError(ERROR)
        cases.append(Case(c["caseId"], split, question, domains, tuple(requirements), refs))
        families[split].update(by_id[s].family for s in refs)
    if families["development"] & families["holdout"] or {s for c in cases for s in c.sources} != set(by_id):
        raise ValueError(ERROR)
    result = Dataset(hashlib.sha256(raw).hexdigest(), _text(root["bindingSha256"], r"[0-9a-f]{64}"),
                     tuple(sources), tuple(cases))
    if result.limits != {"search": 54, "embedding": 27, "rerank": 29}:
        raise ValueError(ERROR)
    return result
