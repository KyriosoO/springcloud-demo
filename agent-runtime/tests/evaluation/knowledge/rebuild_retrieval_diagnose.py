"""Bounded offline loss diagnosis (DR-KRET-401/402); never an online tool.

The B reader verifies frozen Git blobs and finite trace/inventory hashes. Missing
observations stay unknown, and this module neither reconstructs historical ACL
decisions nor authorizes an experiment. Literal lookup accepts only an explicitly
approved, hash-bound in-memory source set; it cannot read arbitrary directories.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Literal, cast

from tests.evaluation.knowledge import rebuild_b_review as review
from tests.evaluation.knowledge import rebuild_b_reuse_binding as reuse
from tests.evaluation.knowledge.rebuild_b_comparator import ArmTrace, CandidateRef, ComparisonCase

Stage = Literal["keyword", "vector", "rrf", "rerank", "final20", "evidence"]
_STAGES = ("keyword", "vector", "rrf", "rerank", "final20", "evidence")
_DOMAINS = ("tax.policy", "tax.law")


class DiagnosisError(ValueError):
    def __init__(self) -> None:
        super().__init__("diagnosis_input_invalid")


def _require(condition: bool) -> None:
    if not condition:
        raise DiagnosisError()


@dataclass(frozen=True, slots=True)
class Observation:
    stage: Stage
    domain: str
    # None means no record. An empty tuple is a confirmed empty stage.
    ranked: tuple[CandidateRef, ...] | None

    def __post_init__(self) -> None:
        _require(self.stage in _STAGES and self.domain in (*_DOMAINS, "all")
                 and ((self.stage in ("keyword", "vector", "rerank") and self.domain in _DOMAINS)
                      or (self.stage in ("rrf", "final20", "evidence") and self.domain == "all")))
        if self.ranked is not None:
            maximum = 20 if self.stage in ("keyword", "vector", "final20") else 80
            _require(type(self.ranked) is tuple and len(self.ranked) <= maximum
                     and all(type(ref) is CandidateRef for ref in self.ranked)
                     and len(set(self.ranked)) == len(self.ranked)
                     and len({(ref.document_id, ref.chunk_id) for ref in self.ranked})
                     == len(self.ranked))


def diagnose_source(*, source: CandidateRef, source_domain: str,
                    selected_domains: tuple[str, ...],
                    inventory: tuple[CandidateRef, ...] | None,
                    observations: tuple[Observation, ...]) -> dict[str, object]:
    """Identify observed loss, not its unobserved algorithm/ACL root cause."""
    _require(type(source) is CandidateRef and source_domain in _DOMAINS
             and type(selected_domains) is tuple and bool(selected_domains)
             and len(set(selected_domains)) == len(selected_domains)
             and all(domain in _DOMAINS for domain in selected_domains)
             and type(observations) is tuple and len(observations) <= 10
             and all(type(item) is Observation for item in observations)
             and len({(item.stage, item.domain) for item in observations}) == len(observations))
    inventory_state = "unknown"
    if inventory is not None:
        _require(type(inventory) is tuple and len(inventory) <= 22000
                 and all(type(ref) is CandidateRef for ref in inventory)
                 and len({(ref.document_id, ref.chunk_id) for ref in inventory}) == len(inventory))
        # Same identity with another hash is drift, not a missing source.
        _require(not any(ref.document_id == source.document_id and ref.chunk_id == source.chunk_id
                         and ref.content_sha256 != source.content_sha256 for ref in inventory))
        inventory_state = "present" if source in inventory else "absent"
    rows: list[dict[str, object]] = []
    states: dict[str, str] = {}
    for stage in _STAGES:
        domain = "all" if stage in ("rrf", "final20", "evidence") else source_domain
        observation = next((item for item in observations
                            if (item.stage, item.domain) == (stage, domain)), None)
        ranked = None if observation is None else observation.ranked
        if ranked is not None:
            _require(not any(ref.document_id == source.document_id and ref.chunk_id == source.chunk_id
                             and ref.content_sha256 != source.content_sha256 for ref in ranked))
        state = "missing_record" if ranked is None else "hit" if source in ranked else "no_hit"
        rank = ranked.index(source) + 1 if ranked is not None and source in ranked else None
        states[stage] = state
        rows.append({"stage": stage, "domain": domain, "state": state, "rank": rank})
    # Later stages cannot invent a source excluded by their complete recorded input.
    for inputs, output in ((('keyword', 'vector'), 'rrf'),
                           (('rrf',), 'rerank'), (('rerank',), 'final20'),
                           (('final20',), 'evidence')):
        _require(not (all(states[key] == "no_hit" for key in inputs)
                      and states[output] == "hit"))
    if inventory_state == "absent":
        _require(not any(state == "hit" for state in states.values()))
        loss = "absent_frozen_inventory"
    elif source_domain not in selected_domains:
        _require(not any(state == "hit" for state in states.values()))
        loss = "domain_not_selected"
    elif states["keyword"] == states["vector"] == "no_hit":
        loss = "initial_recall_or_prior" if inventory_state == "present" else "source_provenance_unknown"
    else:
        loss = "unknown"
        for inputs, output in ((('keyword', 'vector'), 'rrf'),
                               (('rrf',), 'rerank'), (('rerank',), 'final20'),
                               (('final20',), 'evidence')):
            if any(states[key] == "hit" for key in inputs) and states[output] == "no_hit":
                loss = f"excluded_at_{output}"
                break
        if loss == "unknown" and states["final20"] == "hit":
            loss = "retained_in_final20"
    return {"source": {"documentId": source.document_id, "chunkId": source.chunk_id,
                       "contentSha256": source.content_sha256},
            "sourceDomain": source_domain, "inventory": inventory_state,
            "observedLoss": loss, "rootCause": "unknown", "authorization": "unknown",
            "filterDecision": "unknown", "answerQuality": "not_assessed", "stages": rows}


@dataclass(frozen=True, slots=True)
class ApprovedPublicText:
    """Caller supplies a previously approved source; this is not ACL proof."""
    source: CandidateRef
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        _require(type(self.source) is CandidateRef and type(self.text) is str
                 and 0 < len(self.text.encode("utf-8")) <= 65536
                 and sha256(self.text.encode("utf-8")).hexdigest() == self.source.content_sha256)


def locate_literals(*, sources: tuple[ApprovedPublicText, ...], terms: tuple[str, ...],
                    max_results: int = 16) -> dict[str, object]:
    """Literal-only lookup; return IDs/hash/span/term ordinal, never source text."""
    _require(type(sources) is tuple and 0 < len(sources) <= 30
             and all(type(item) is ApprovedPublicText for item in sources)
             and len({(item.source.document_id, item.source.chunk_id) for item in sources}) == len(sources)
             and type(terms) is tuple and 0 < len(terms) <= 16
             and all(type(term) is str and 0 < len(term) <= 128
                     and all(ord(char) >= 32 for char in term) for term in terms)
             and len(set(terms)) == len(terms) and type(max_results) is int
             and 1 <= max_results <= 32)
    hits: list[dict[str, object]] = []
    for item in sources:
        for ordinal, term in enumerate(terms, 1):
            offset = 0
            while (position := item.text.find(term, offset)) != -1:
                if len(hits) == max_results:
                    return {"hits": hits, "truncated": True, "sourceCount": len(sources),
                            "termCount": len(terms)}
                hits.append({"documentId": item.source.document_id, "chunkId": item.source.chunk_id,
                             "contentSha256": item.source.content_sha256, "termOrdinal": ordinal,
                             "start": position, "end": position + len(term)})
                offset = position + len(term)
    return {"hits": hits, "truncated": False, "sourceCount": len(sources), "termCount": len(terms)}


def _b_observations(case: ComparisonCase, arm: ArmTrace) -> tuple[Observation, ...]:
    """Admit recorded B stage shapes against the actual frozen plan, not hints."""
    domains = case.plan.selected_domain_ids
    path_limit, final_limit = (case.plan.settings.per_path_candidate_limit,
                               case.plan.settings.final_candidate_limit)
    observed: list[Observation] = []
    pools: dict[str, set[CandidateRef]] = {domain: set() for domain in domains}
    for stage, entries in (("keyword", arm.keyword), ("vector", arm.vector)):
        _require(tuple(item.domain_id for item in entries) == domains
                 and all(item.path == stage and len(item.ranked) <= path_limit for item in entries))
        for item in entries:
            observed.append(Observation(cast(Stage, stage), item.domain_id, item.ranked))
            pools[item.domain_id].update(item.ranked)
    _require(set(arm.fused) == set().union(*pools.values())
             and len(arm.fused) <= path_limit * len(case.plan.items))
    expected_rerank = tuple(domain for domain in domains if pools[domain])
    _require(tuple(item.domain_id for item in arm.reranked) == expected_rerank)
    for item in arm.reranked:
        _require(item.path == "rerank" and len(item.ranked) <= path_limit * 2
                 and set(item.ranked) == pools[item.domain_id])
        observed.append(Observation("rerank", item.domain_id, item.ranked))
    _require(len(arm.final20) == min(len(arm.fused), final_limit)
             and set(arm.final20) <= set(arm.fused))
    return tuple(observed) + (Observation("rrf", "all", arm.fused),
                              Observation("final20", "all", arm.final20))


def diagnose_b(directory: Path) -> dict[str, object]:
    """Replay an admitted B trace; no new index read or human label is generated."""
    try:
        loaded = review.load_completed(directory)
        fixture_raw = reuse.git_blob(loaded.frozen_head, reuse.FIXTURE_PATH)
        _require(sha256(fixture_raw).hexdigest() == loaded.spec.uat_fixture_sha256)
        # The frozen dataset is pretty-printed, not a canonical sidecar; its
        # strict fields/duplicate keys were already admitted by _frozen_spec.
        fixture = json.loads(fixture_raw)
        domains: dict[CandidateRef, str] = {}
        for item in fixture["sources"]:
            ref = CandidateRef(item["documentId"], item["chunkId"], item["contentSha256"])
            _require(item["domainId"] in _DOMAINS and ref not in domains)
            domains[ref] = item["domainId"]
        output: list[dict[str, object]] = []
        for case_ordinal, (case, trace) in enumerate(zip(loaded.spec.cases, loaded.run.cases, strict=True)):
            for arm, mapping in ((trace.baseline, loaded.old.source_map),
                                 (trace.candidate, loaded.old.candidate_map)):
                inventory = tuple(CandidateRef(item.document_id, item.chunk_id, item.content_sha256)
                                  for item in mapping.records)
                observed = _b_observations(case, arm)
                for source in case.necessary_sources:
                    domain = domains[source]
                    # The admitted B arms bind both domains to the same physical
                    # corpus; existence in this map still does not prove ACL or
                    # category admission for either logical domain.
                    diagnosis = diagnose_source(source=source, source_domain=domain,
                        selected_domains=case.plan.selected_domain_ids,
                        inventory=inventory,
                        observations=observed)
                    output.append({"caseId": case.case_id, "arm": arm.arm,
                                   "evidencePointer": f"/traces/{case_ordinal}/{arm.arm}", **diagnosis})
        return {"schemaVersion": 1, "runId": directory.resolve().name,
                "frozenHead": loaded.frozen_head, "comparisonResultSha256": loaded.result_sha256,
                "sourceMapSha256": loaded.old.source_map.sha256,
                "candidateMapSha256": loaded.old.candidate_map.sha256,
                "newExternalCalls": 0, "historicalOutcomeUnchanged": True,
                "onlineChangeSelected": False, "diagnoses": output}
    except (review.ReviewError, reuse.ReuseBindingError, DiagnosisError, ValueError,
            TypeError, KeyError, UnicodeError, OSError, AttributeError):
        raise DiagnosisError() from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    try:
        output = diagnose_b(args.run_directory)
    except DiagnosisError:
        print(json.dumps({"status": "not_assessed", "reason": "diagnosis_input_invalid"}))
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
