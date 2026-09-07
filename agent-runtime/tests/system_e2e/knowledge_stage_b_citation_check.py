"""Post-execution source binding; no online imports, I/O, or historical replay.

The caller supplies the request-local verified bundle, the actual policy-filtered
Summary input, and validated public points. These values stay in memory. Only
the finite verdict may be retained. This does not replace semantic usefulness,
domain, task, budget, or safety checks and is not an executable live runner.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re

from agent_runtime.knowledge.evidence.contracts import KnowledgeEvidenceBundle, KnowledgeSummaryInput


CHECK_VERSION = "stage-b-citation-binding-v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_GOLD_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}")


@dataclass(frozen=True, slots=True)
class CitationCheck:
    binding_valid: bool
    required_clauses: tuple[tuple[str, bool], ...]
    failure_reason: str | None


def check_citations(
    *, bundle: KnowledgeEvidenceBundle, summary_input: KnowledgeSummaryInput,
    points: object, required: Mapping[str, Mapping[str, str]],
) -> CitationCheck:
    """Bind each quote to its cited source, not any matching text in the pool."""
    # Gold is frozen by the caller before execution; malformed gold is a harness
    # error, not a model failure, and must never produce a passing empty check.
    if (not isinstance(required, Mapping) or not 1 <= len(required) <= 5 or any(
        type(name) is not str or _GOLD_NAME.fullmatch(name) is None
        or not isinstance(gold, Mapping)
        or set(gold) != {"chunk", "sha256", "clause"}
        or any(type(value) is not str or not value for value in gold.values())
        or _SHA256.fullmatch(gold["sha256"]) is None
        or len(gold["clause"]) > 512 for name, gold in required.items()
    )):
        raise ValueError("stage_b.invalid_source_gold")
    failed = tuple((name, False) for name in required)

    def reject(reason: str) -> CitationCheck:
        return CitationCheck(False, failed, reason)

    evidence = bundle.evidence
    if (not 1 <= len(evidence) <= 8 or len(summary_input.evidence) != len(evidence)
            or type(summary_input.schema_version) is not int or summary_input.schema_version != 1
            or type(summary_input.coverage.retrieval_complete) is not bool
            or type(summary_input.coverage.domain_coverage_complete) is not bool
            or summary_input.question != bundle.question_trace.minimized_question
            or summary_input.coverage.retrieval_complete != bundle.coverage.retrieval_complete
            or summary_input.coverage.domain_coverage_complete != (not bundle.coverage.missing_domain_ids)):
        return reject("input_binding_invalid")
    by_ref = {item.evidence_ref: item for item in summary_input.evidence}
    if set(by_ref) != {f"e{i}" for i in range(1, len(evidence) + 1)}:
        return reject("input_binding_invalid")
    by_id = {item.evidence_id: item for item in evidence}
    if len(by_id) != len(evidence):
        return reject("input_binding_invalid")
    for ordinal, source in enumerate(evidence, 1):
        model_source = by_ref[f"e{ordinal}"]
        if (model_source.content != source.content
                or hashlib.sha256(source.content.encode("utf-8")).hexdigest() != source.content_sha256
                or model_source.domain_ids is not None and model_source.domain_ids != source.domain_ids):
            return reject("input_binding_invalid")
    if type(points) is not list or not 1 <= len(points) <= 5:
        return reject("citation_invalid")
    seen: set[str] = set()
    hits: set[str] = set()
    for point in points:
        if type(point) is not dict:
            return reject("citation_invalid")
        quote, citation = point.get("quote"), point.get("citation")
        if (type(quote) is not str or not 1 <= len(quote) <= 512
                or any(ord(c) < 32 or ord(c) == 127 for c in quote)
                or type(citation) is not dict):
            return reject("citation_invalid")
        evidence_id, domains = citation.get("evidenceId"), citation.get("domainIds")
        if type(evidence_id) is not str or evidence_id not in by_id or evidence_id in seen:
            return reject("citation_invalid")
        source = by_id[evidence_id]
        if type(domains) is not list or domains != list(source.domain_ids) or quote not in source.content:
            return reject("citation_invalid")
        seen.add(evidence_id)
        hits.update(name for name, gold in required.items()
                    if source.chunk_id == gold["chunk"]
                    and source.content_sha256 == gold["sha256"] and gold["clause"] in quote)
    checks = tuple((name, name in hits) for name in required)
    return CitationCheck(True, checks, None if all(value for _, value in checks) else "required_source_not_cited")
