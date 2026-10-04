"""Private execution seams; no launcher, default connection, or authorization.

Actual HTTP adapters can use these guards only inside a separately approved
owned lifecycle. Tests inject in-memory delegates. Nothing here creates an
HTTP client, reads credentials, starts a process, or writes a run asset.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from hashlib import sha256
import math
import re
from threading import Lock
from typing import Callable

from agent_runtime.knowledge.retrieval.http import (
    BoundedHttpRequest, BoundedHttpResponse, KnowledgeHttpTransport,
)
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_b_local_transport import _request_hashes


@dataclass(frozen=True, slots=True)
class BudgetPlan:
    """Conditional forecast, never a real operation grant or current inventory."""
    record_count: int
    preparation_scans: int = 1

    def __post_init__(self) -> None:
        p.require(type(self.record_count) is int and 1 <= self.record_count <= 22000
                  and type(self.preparation_scans) is int and self.preparation_scans in (0, 1),
                  "budget_input_invalid")

    def rows(self) -> tuple[tuple[str, int], ...]:
        per_scan = 1 + math.ceil(self.record_count / 250)
        return (("snapshotPreparation", self.preparation_scans * per_scan),
                ("preparationMetadata", self.preparation_scans * 3),
                ("snapshotPrePost", 2 * per_scan), ("metadata", 18),
                ("physicalSearch", 44), ("typedSearch", 44),
                ("queryEmbedding", 10), ("rerank", 22), ("prewarmRerank", 1),
                ("javaHealth", 40), ("bgeHealth", 4))

    def preview(self) -> dict[str, object]:
        rows = dict(self.rows())
        return {"kind": "document_number_execution_budget_draft_v1",
                "realExecutionAllowed": False, "recordCount": self.record_count,
                "inventoryCountStatus": "declared_not_observed", "scanPageSize": 250,
                "limits": rows,
                "esHttpUpperBound": sum(rows[k] for k in (
                    "snapshotPreparation", "preparationMetadata", "snapshotPrePost", "metadata", "physicalSearch")),
                "allHttpUpperBound": sum(rows.values()),
                "forbidden": dict.fromkeys(p.FORBIDDEN, 0),
                "unresolved": ["exact_run_and_authorization", "current_snapshots_and_exclusive_window",
                    "owned_startup_and_cleanup", "model_identity_non_http_budget",
                    "offline_actual_java_keyword_projection", "blind_labels"],
                "interpretation": "includes_separate_fresh_capture_then_frozen_pre_and_post_checks;"
                    "not_measured_counts;startup_shape_must_be_attested"}


@dataclass(frozen=True, slots=True)
class Attempt:
    kind: str
    label: str
    request_sha256: str
    outcome: str = "pending"
    http_status: int | None = None


class AttemptLedger:
    """Reserve at the physical send boundary; failures never restore the budget."""
    def __init__(self, limits: tuple[tuple[str, int], ...], *,
                 checkpoint: Callable[[str, int | None, Attempt | None], None] | None = None) -> None:
        valid = set(dict(BudgetPlan(1).rows()))
        p.require(type(limits) is tuple and bool(limits) and len(dict(limits)) == len(limits)
                  and all(k in valid and type(n) is int and 0 <= n <= 400 for k, n in limits),
                  "ledger_limits_invalid")
        p.require(checkpoint is None or callable(checkpoint), "ledger_checkpoint_invalid")
        self.limits = dict(limits)
        self.counts = dict.fromkeys(self.limits, 0)
        self.events: list[Attempt] = []
        self._seen: set[tuple[str, str]] = set()
        self._lock = Lock()
        self._stopped = False
        self._writer = checkpoint

    def _checkpoint(self, event: str, ticket: int | None, attempt: Attempt | None) -> None:
        failed = False
        if self._writer is not None:
            try:
                self._writer(event, ticket, attempt)
            except Exception:
                failed = True
        if failed:
            self._stopped = True
            raise p.ProtocolError("attempt_journal_failed")

    def begin(self, kind: str, label: str, body: bytes) -> int:
        p.require(type(label) is str and re.fullmatch(r"[A-Za-z0-9._:/-]{1,256}", label) is not None
                  and type(body) is bytes and len(body) <= 2 * 1024 * 1024, "attempt_input_invalid")
        with self._lock:
            p.require(not self._stopped, "attempt_batch_stopped")
            p.require(kind in self.limits and self.counts[kind] < self.limits[kind], "attempt_budget_exceeded")
            p.require((kind, label) not in self._seen, "attempt_retry_forbidden")
            self._seen.add((kind, label))
            self.counts[kind] += 1
            self.events.append(Attempt(kind, label, sha256(body).hexdigest()))
            ticket = len(self.events) - 1
            self._checkpoint("started", ticket, self.events[ticket])
            return ticket

    def finish(self, ticket: int, outcome: str, status: int | None = None) -> None:
        p.require(type(ticket) is int and 0 <= ticket < len(self.events)
                  and outcome in ("completed", "transport_failed", "cancelled")
                  and (status is None or type(status) is int and 100 <= status <= 599)
                  and ((outcome == "completed") == (status is not None)), "attempt_receipt_invalid")
        with self._lock:
            event = self.events[ticket]
            p.require(event.outcome == "pending", "attempt_already_finished")
            receipt = Attempt(event.kind, event.label, event.request_sha256, outcome, status)
            # A failed durable receipt remains pending, never falsely completed.
            self._checkpoint("finished", ticket, receipt)
            self.events[ticket] = receipt
            if outcome != "completed" or status != 200:
                self._stopped = True

    def abort(self) -> None:
        """Protocol failure also blocks new sends; in-flight receipts may finish."""
        with self._lock:
            if not self._stopped:
                self._stopped = True
                self._checkpoint("stopped", None, None)

    def view(self) -> dict[str, object]:
        with self._lock:
            return {"counts": dict(self.counts), "stopped": self._stopped,
                    "pending": sum(e.outcome == "pending" for e in self.events),
                    "events": [asdict(e) for e in self.events]}


class CountedKnowledgeTransport:
    """Meter the existing production adapters, not a second DTO/decoder path."""
    def __init__(self, *, delegate: KnowledgeHttpTransport, ledger: AttemptLedger,
                 case: p.ComparisonCase, arm: str, kind: str,
                 domain: str | None = None, vector: tuple[float, ...] | None = None) -> None:
        p.require(type(case) is p.ComparisonCase and arm in (*p.ARMS, "shared")
                  and kind in ("typedSearch", "queryEmbedding", "rerank")
                  and (domain is None or domain in case.plan.selected_domain_ids)
                  and (kind != "queryEmbedding" or arm == "shared" and domain is None)
                  and (kind != "rerank" or arm in p.ARMS and domain is not None)
                  and (kind != "typedSearch" or arm in p.ARMS and domain is None
                       and type(vector) is tuple and len(vector) == 1024
                       and all(type(v) is float and math.isfinite(v) for v in vector)),
                  "adapter_binding_invalid")
        self.delegate, self.ledger = delegate, ledger
        self.case, self.arm, self.kind = case, arm, kind
        self.question, self.domain, self.vector = case.plan.original_question, domain, vector

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        path = {"typedSearch": "/es/knowledge/search", "queryEmbedding": "/embed", "rerank": "/rerank"}[self.kind]
        p.require(type(request) is BoundedHttpRequest and request.method == "POST"
                  and request.relative_path == path and type(timeout_s) in (int, float)
                  and not isinstance(timeout_s, bool) and math.isfinite(timeout_s) and 0 < timeout_s <= 5
                  and type(request.max_response_bytes) is int and 0 < request.max_response_bytes <= 2 * 1024 * 1024,
                  "adapter_request_invalid")
        headers = dict(request.headers)
        expected_headers = {"Accept-Encoding", "Content-Type"} | ({"Authorization"} if self.kind == "typedSearch" else set())
        p.require(len(headers) == len(request.headers) and set(headers) == expected_headers
                  and headers["Accept-Encoding"] == "identity" and headers["Content-Type"] == "application/json"
                  and (self.kind != "typedSearch" or type(headers["Authorization"]) is str
                       and headers["Authorization"].startswith("Bearer ")
                       and 8 <= len(headers["Authorization"]) <= 8192
                       and "\r" not in headers["Authorization"] and "\n" not in headers["Authorization"]),
                  "adapter_headers_invalid")
        body = p._decode(request.body)
        label = f"{self.case.case_id}/{self.arm}"
        if self.kind == "typedSearch":
            domain = body.get("logicalDomainId")
            route = body.get("path")
            p.require(set(body) == {"schemaVersion", "logicalDomainId", "retrievalProfileId", "path",
                                   "queryText", "queryVector", "limit"}
                      and type(body["schemaVersion"]) is int and body["schemaVersion"] == 1
                      and type(body["limit"]) is int and body["limit"] == 20
                      and domain in self.case.plan.selected_domain_ids and route in ("keyword", "vector")
                      and body["retrievalProfileId"] == {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}[domain]
                      and (body["queryText"] == self.question and body["queryVector"] is None if route == "keyword"
                           else body["queryText"] is None and type(body["queryVector"]) is list
                           and all(type(v) in (int, float) and math.isfinite(v) for v in body["queryVector"])
                           and tuple(body["queryVector"]) == self.vector), "adapter_payload_drift")
            label += f"/{domain}/{route}"
        elif self.kind == "queryEmbedding":
            p.require(set(body) == {"texts"} and body["texts"] == [self.question], "adapter_payload_drift")
        else:
            p.require(set(body) == {"query", "documents", "top_n", "normalize"}
                      and body["query"] == self.question and type(body["documents"]) is list
                      and 1 <= len(body["documents"]) <= 40
                      and all(type(t) is str and 1 <= len(t) <= 4700 for t in body["documents"])
                      and type(body["top_n"]) is int and body["top_n"] == len(body["documents"])
                      and body["normalize"] is True, "adapter_payload_drift")
            label += f"/{self.domain}"
        ticket = self.ledger.begin(self.kind, label, request.body)
        response: BoundedHttpResponse | None = None
        failed = False
        cancelled = False
        try:
            response = await self.delegate.send(request=request, timeout_s=timeout_s)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            failed = True
        # Raise outside the handler so raw provider exception context is absent.
        if cancelled:
            self.ledger.finish(ticket, "cancelled")
            raise asyncio.CancelledError
        if failed:
            self.ledger.finish(ticket, "transport_failed")
            raise p.ProtocolError("adapter_transport_failed")
        if type(response) is not BoundedHttpResponse or type(response.status_code) is not int or not 100 <= response.status_code <= 599:
            self.ledger.finish(ticket, "transport_failed")
            raise p.ProtocolError("adapter_response_invalid")
        self.ledger.finish(ticket, "completed", response.status_code)
        if (response.status_code != 200 or response.content_type != "application/json"
                or response.content_encoding not in (None, "identity")
                or type(response.body) is not bytes or not 0 < len(response.body) <= request.max_response_bytes):
            self.ledger.abort()
            raise p.ProtocolError("adapter_response_invalid")
        return response  # Production decoder still decides JSON/DTO validity.


POLICY_CATEGORIES = ("税务规范性文件", "财税文件", "工作通知", "其他文件", "政策解读", "税务部门规章", "国务院文件", "curated")
LAW_CATEGORIES = ("法律", "行政法规")
SOURCE_FIELDS = tuple(sorted(("documentId", "chunkId", "title", "content", "sourceUrl", "documentNo",
                              "writtenDate", "materialType", "aclRef")))


@dataclass(frozen=True, slots=True)
class PhysicalWitness:
    case_id: str
    arm: str
    domain: str
    path: str
    request_sha256: str
    canonical_sha256: str
    http_status: int


class PhysicalSearchGate:
    """Case-bound physical search seam for a future owned proxy; no listener."""
    def __init__(self, *, case: p.ComparisonCase, arm: str, read_alias: str,
                 vector: tuple[float, ...], ledger: AttemptLedger,
                 keyword_sha256: tuple[tuple[str, str], ...]) -> None:
        p.require(type(case) is p.ComparisonCase and arm in p.ARMS
                  and type(read_alias) is str and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", read_alias) is not None
                  and type(vector) is tuple and len(vector) == 1024
                  and all(type(v) is float and math.isfinite(v) for v in vector), "physical_binding_invalid")
        p.require(type(keyword_sha256) is tuple and len(keyword_sha256) == len(case.plan.selected_domain_ids)
                  and tuple(d for d, _ in keyword_sha256) == case.plan.selected_domain_ids
                  and all(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                          for _, digest in keyword_sha256), "physical_projection_binding_invalid")
        self.case, self.arm, self.read_alias, self.vector, self.ledger = case, arm, read_alias, vector, ledger
        # A real caller must separately attest that these case/arm projections
        # were generated by the frozen Java build, not by the captured request.
        self.keyword_sha256 = dict(keyword_sha256)
        self.witnesses: list[PhysicalWitness] = []

    def forward(self, *, method: str, path: str, body: bytes,
                send: Callable[[bytes], BoundedHttpResponse]) -> BoundedHttpResponse:
        p.require(method == "POST" and path == f"/{self.read_alias}/_search", "physical_route_forbidden")
        value = p._decode(body)
        p.require(value.get("_source") == {"includes": list(SOURCE_FIELDS)}
                  and value.get("track_total_hits") is False
                  and type(value.get("size")) is int and value["size"] == 21, "physical_projection_drift")
        if set(value) == {"_source", "track_total_hits", "size", "knn"}:
            query = value["knn"]
            p.require(type(query) is dict and set(query) == {"field", "query_vector", "k", "num_candidates", "filter"}
                      and query["field"] == "embedding" and type(query["k"]) is int and query["k"] == 21
                      and type(query["num_candidates"]) is int and query["num_candidates"] == 100
                      and type(query["query_vector"]) is list
                      and all(type(v) in (int, float) and math.isfinite(v) for v in query["query_vector"])
                      and tuple(query["query_vector"]) == self.vector, "physical_vector_drift")
            category, route = query["filter"], "vector"
        else:
            p.require(set(value) == {"_source", "track_total_hits", "size", "query"}
                      and type(value["query"]) is dict and set(value["query"]) == {"bool"}, "physical_keyword_drift")
            query = value["query"]["bool"]
            p.require(type(query) is dict and type(query.get("filter")) is list and len(query["filter"]) == 1,
                      "physical_filter_drift")
            category, route = query["filter"][0], "keyword"
            multi = {"multi_match": {"query": self.case.plan.original_question, "fields": ["title", "content", "section"]}}
            if set(query) == {"filter", "must"}:
                p.require(query["must"] == [multi], "physical_keyword_drift")
            else:
                p.require(set(query) == {"filter", "should", "minimum_should_match"}
                          and type(query["minimum_should_match"]) is int and query["minimum_should_match"] == 1
                          and type(query["should"]) is list and len(query["should"]) == 2
                          and query["should"][0] == multi, "physical_keyword_drift")
                self._metadata_signal(query["should"][1])
        domain = next((d for d, categories in (("tax.policy", POLICY_CATEGORIES), ("tax.law", LAW_CATEGORIES))
                       if category == {"terms": {"channel": list(categories)}}), None)
        p.require(domain in self.case.plan.selected_domain_ids, "physical_domain_drift")
        p.require(domain != "tax.law" or route != "keyword" or set(query) == {"filter", "must"},
                  "physical_law_signal_forbidden")
        assert domain is not None
        raw_hash, canonical_hash = _request_hashes(method, body)
        p.require(route != "keyword" or canonical_hash == self.keyword_sha256[domain],
                  "physical_keyword_projection_drift")
        ticket = self.ledger.begin("physicalSearch", f"{self.case.case_id}/{self.arm}/{domain}/{route}", body)
        response: BoundedHttpResponse | None = None
        failed = False
        try:
            response = send(body)  # Original bytes, never a reconstructed ES query.
        except Exception:
            failed = True
        if failed:
            self.ledger.finish(ticket, "transport_failed")
            raise p.ProtocolError("physical_transport_failed")
        if type(response) is not BoundedHttpResponse or type(response.status_code) is not int or not 100 <= response.status_code <= 599:
            self.ledger.finish(ticket, "transport_failed")
            raise p.ProtocolError("physical_response_invalid")
        self.ledger.finish(ticket, "completed", response.status_code)
        assert domain is not None
        self.witnesses.append(PhysicalWitness(self.case.case_id, self.arm, domain, route,
                                              raw_hash, canonical_hash, response.status_code))
        if (response.status_code != 200 or response.content_type != "application/json"
                or response.content_encoding not in (None, "identity")
                or type(response.body) is not bytes or not 0 < len(response.body) <= 2 * 1024 * 1024):
            self.ledger.abort()
            raise p.ProtocolError("physical_response_invalid")
        return response

    @staticmethod
    def _metadata_signal(value: object) -> None:
        p.require(type(value) is dict and set(value) == {"constant_score"}, "physical_signal_invalid")
        # Checked nesting avoids accepting an unknown clause as a document-number boost.
        assert isinstance(value, dict)
        score = value["constant_score"]
        p.require(type(score) is dict and set(score) == {"filter", "boost"} and type(score["boost"]) is int
                  and score["boost"] == 100 and type(score["filter"]) is dict
                  and set(score["filter"]) == {"bool"}, "physical_signal_invalid")
        inner = score["filter"]["bool"]
        p.require(type(inner) is dict and set(inner) == {"should", "minimum_should_match"}
                  and type(inner["minimum_should_match"]) is int and inner["minimum_should_match"] == 1
                  and type(inner["should"]) is list and 1 <= len(inner["should"]) <= 4, "physical_signal_invalid")
        for match in inner["should"]:
            p.require(type(match) is dict and set(match) == {"regexp"} and type(match["regexp"]) is dict
                      and set(match["regexp"]) == {"documentNo"}, "physical_signal_invalid")
            regex = match["regexp"]["documentNo"]
            p.require(type(regex) is dict and set(regex) == {"value", "flags", "case_insensitive", "max_determinized_states"}
                      and type(regex["value"]) is str and 1 <= len(regex["value"]) <= 900
                      and regex["flags"] == "NONE" and regex["case_insensitive"] is False
                      and type(regex["max_determinized_states"]) is int and regex["max_determinized_states"] == 256,
                      "physical_signal_invalid")
            parts = regex["value"].split("[ 　]*")
            p.require(2 <= len(parts) <= 80 and all(part in (r"\[", r"\]", "〔", "〕")
                or len(part) == 1 and (part.isalpha() or part.isdecimal()) for part in parts),
                "physical_signal_invalid")
