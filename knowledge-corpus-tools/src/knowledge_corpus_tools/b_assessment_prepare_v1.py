"""Read-only, bounded preparation of the frozen B representation intent.

This scoped preflight never writes ES, calls BGE, or retains corpus text.  The
separate full-source scan and builder remain the authorities for the complete
source fingerprint and candidate contents.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .b_candidate_freeze_v1 import (
    BFreezeError, GitState, _budget, _check_git, _git_fixture_blob,
    _git_source_build_blob, _id_mapping, _intent, _profile_snapshot,
    _scan_budget, _verify_fixture_blob, _verify_source_build_evidence,
)
from .errors import ContractError
from .rechunk_candidate_v1 import _write_blocked
from .retrieval_representation_v2 import build_retrieval_representation_v2
from .vector_candidate import (POLICY_CATEGORIES, _reject_constant, _unique_pairs,
                               canonical_bytes, mapping_fingerprint)
from .vector_representation import build_vector_representation

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RUN = re.compile(r"[a-z0-9][a-z0-9-]{4,95}\Z")
_RESOURCE = re.compile(r"[a-z0-9][a-z0-9._-]{0,127}\Z")
_MAX_RESPONSE = 8 * 1024 * 1024
_PAGE = 250
_COMPARISON_METADATA_ES_HTTP = 30
_SOURCE_BUILD_DIRECTORY = "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2"
_SOURCE_BUILD_PATHS = (f"{_SOURCE_BUILD_DIRECTORY}/binding.json",
                       f"{_SOURCE_BUILD_DIRECTORY}/result.json")
_CANDIDATE_KEYS = frozenset({
    "source_index", "source_uuid", "source_mapping_sha256", "source_fingerprint",
    "source_count", "read_alias", "online_index", "online_uuid",
    "online_mapping_sha256", "alias_snapshot_sha256", "candidate_index",
    "target_mapping_version", "target_mapping_sha256", "baseline_model_snapshot",
    "model_snapshot", "tokenizer_sha256", "baseline_representation_version",
})
_MANIFEST_SHA256 = "c64c1cc69636bdfad6dbca2e9f127f8ccd9855e3baeabf70a6bc5fdd0405d01c"
_SELECTED_ASSETS = (
    ("asset-0b9c99e7dfb27c8e600743d7", "0b9c99e7dfb27c8e600743d7a399e34dc244c9794f434c716d67952a0ff12559", 342),
    ("asset-5cac035a23b63ebf01ea1a3e", "5cac035a23b63ebf01ea1a3ed58eb4c39d2819c19783a7c046e82ee33b41fd0e", 149),
    ("asset-9ddc228c43d9e2758c5c0db2", "9ddc228c43d9e2758c5c0db2e5d18ccff7b6657a19f0f42f4d5977c51518c1c9", 187),
    ("asset-45bb466b54ad7d636c7a0abb", "45bb466b54ad7d636c7a0abb4b9f9d0f031351d82dfc8481077fc2627419943f", 60),
)
_SELECTED_COUNTS = tuple(item[2] for item in _SELECTED_ASSETS)
_PARENT_DOCUMENT_ID = "tax-50abf52b7a181b8974c97fd4"
_THRESHOLDS: dict[str, object] = {
    "macroRecallStrictlyImproves": True, "macroPrecisionNoRegression": True,
    "medianLatencyRatioMax": 1.1, "coreAndRetainedNoRegression": True,
    "missingBlindLabel": "not_assessed", "unexplainedKeywordDrift": "not_assessed",
}
_CASE_IDS = tuple(f"UAT-KM-{number:03d}" for number in (1, 2, 3, 5, 6, 7, 8, 9, 11, 12))


class BPrepareError(Exception):
    """Finite, content-free refusal reason."""

    def __init__(self, reason: str) -> None:
        self.reason = reason if reason in {
            "input_invalid", "source_drift", "source_record_invalid", "budget_exhausted",
            "http_failed", "binding_invalid",
        } else "input_invalid"
        super().__init__(self.reason)


@dataclass(frozen=True, slots=True)
class PreparedBIntent:
    intent_raw: bytes
    preliminary_raw: bytes
    representation_bindings: tuple[dict[str, str], ...]
    scoped_es_http: int
    scoped_es_http_max: int
    source_build_sha256: tuple[str, str]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    if type(value) is not dict:
        raise BPrepareError("input_invalid")
    return value


def _json(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > _MAX_RESPONSE:
        raise BPrepareError("input_invalid")
    value: Any = None
    invalid = False
    try:
        value = json.loads(raw, object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError):
        invalid = True
    if invalid:
        raise BPrepareError("input_invalid")
    return _object(value)


def _require_hash(value: Any) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise BPrepareError("input_invalid")
    return value


def _model_binding(candidate: dict[str, Any]) -> dict[str, str]:
    old = _object(candidate["baseline_model_snapshot"])
    current = _object(candidate["model_snapshot"])
    old_container = _object(old.get("container"))
    current_container = _object(current.get("container"))
    if (set(old) != {"container", "model"} or set(current) != set(old)
            or set(current_container) != set(old_container)
            or type(current_container.get("started")) is not str
            or not current_container["started"]
            or old["model"] != current["model"]
            or {key: value for key, value in old_container.items() if key != "started"}
            != {key: value for key, value in current_container.items() if key != "started"}
            or candidate["baseline_representation_version"] != "policy-title-section-body-v1"):
        raise BPrepareError("binding_invalid")
    return {
        "baselineModelSnapshotSha256": _sha(canonical_bytes(old)),
        "currentModelSnapshotSha256": _sha(canonical_bytes(current)),
        "tokenizerSha256": _require_hash(candidate["tokenizer_sha256"]),
        "baselineRepresentationVersion": "policy-title-section-body-v1",
        "candidateRepresentationVersion": "body-only-v2",
    }


def _selected_assets(selection_raw: bytes, manifest_raw: bytes) -> tuple[tuple[str, str, str, int], ...]:
    selection = _json(selection_raw)
    if (set(selection) != {"schemaVersion", "manifestSha256", "assetIds", "expectedChunkCounts"}
            or selection["schemaVersion"] != 1
            or _sha(manifest_raw) != _MANIFEST_SHA256
            or selection["manifestSha256"] != _sha(manifest_raw)
            or selection["assetIds"] != [item[0] for item in _SELECTED_ASSETS]
            or selection["expectedChunkCounts"] != list(_SELECTED_COUNTS)):
        raise BPrepareError("input_invalid")
    records: dict[str, dict[str, Any]] = {}
    for line in manifest_raw.splitlines():
        record = _json(line)
        asset_id = record.get("asset_id")
        if type(asset_id) is not str or asset_id in records:
            raise BPrepareError("input_invalid")
        records[asset_id] = record
    selected: list[tuple[str, str, str, int]] = []
    for asset_id, version, count in _SELECTED_ASSETS:
        item = records.get(asset_id)
        if (item is None or item.get("detected_mime") != "application/msword"
                or item.get("extension") != ".doc"
                or item.get("asset_version") != version
                or item.get("sha256") != version
                or item.get("parent_document_id") != _PARENT_DOCUMENT_ID):
            raise BPrepareError("input_invalid")
        selected.append((asset_id, version, _PARENT_DOCUMENT_ID, count))
    return tuple(selected)


def _cases(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    sources = {item["id"]: item for item in fixture["sources"]}
    core = fixture["thresholds"]["uat"]["coreCases"]
    cases: list[dict[str, Any]] = []
    for original in fixture["cases"]:
        if not original["retrievalDenominator"]:
            continue
        domains = original["expectedDomains"]
        question = original["question"]
        settings = {"enabledDomainIds": ["tax.policy", "tax.law"],
                    "perPathCandidateLimit": 20, "finalCandidateLimit": 20,
                    "minPartialCandidates": 3, "retrievalTimeoutSeconds": 20.0,
                    "configVersion": "knowledge-minimal-v1"}
        plan = {"schemaVersion": 3, "catalogVersion": "tax-domain-catalog-v2",
                "originalQuestion": question, "queryMode": original["queryMode"],
                "selectedDomainIds": domains,
                "profileBindings": [[domain, {"tax.policy": "tax-policy-v1",
                                              "tax.law": "tax-law-v1"}[domain]]
                                    for domain in domains],
                "settings": settings,
                "items": [{"logicalDomainId": domain, "path": path,
                           "queryText": question, "candidateLimit": 20,
                           "ordinal": index * 2 + offset}
                          for index, domain in enumerate(domains)
                          for offset, path in enumerate(("keyword", "vector"), start=1)]}
        cases.append({
            "caseId": original["caseId"], "queryMode": original["queryMode"],
            "question": question, "selectedDomainIds": domains,
            "core": original["caseId"] in core, "retained": True,
            "necessarySources": [{"documentId": sources[source_id]["documentId"],
                                  "chunkId": sources[source_id]["chunkId"],
                                  "contentSha256": sources[source_id]["contentSha256"]}
                                 for source_id in original["necessarySources"]],
            "plan": plan, "planHash": _sha(canonical_bytes(plan)),
        })
    if tuple(case["caseId"] for case in cases) != _CASE_IDS:
        raise BPrepareError("input_invalid")
    return cases


class _ScopedReader:
    def __init__(self, client: httpx.Client, *, index: str, alias: str,
                 maximum: int) -> None:
        url = client.base_url
        if (url.scheme != "http" or url.host != "127.0.0.1" or url.port != 9200
                or client.follow_redirects or client.trust_env or client.is_closed
                or type(index) is not str or _RESOURCE.fullmatch(index) is None
                or ".." in index or type(alias) is not str
                or _RESOURCE.fullmatch(alias) is None or ".." in alias
                or maximum != 4 + math.ceil(sum(_SELECTED_COUNTS) / _PAGE)):
            raise BPrepareError("input_invalid")
        self.client = client
        self.index = index
        self.alias = alias
        self.maximum = maximum
        self.calls = 0

    def get(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if ((method, path) not in {("GET", f"/{self.index}"),
                                  ("GET", f"/_alias/{self.alias}"),
                                  ("POST", f"/{self.index}/_search")}
                or (method == "POST") != (body is not None)
                or self.calls >= self.maximum):
            raise BPrepareError("budget_exhausted")
        self.calls += 1
        failed = False
        parsed: dict[str, Any] | None = None
        try:
            started = time.monotonic()
            with self.client.stream(method, path,
                    content=None if body is None else canonical_bytes(body),
                    headers={"Content-Type": "application/json"},
                    follow_redirects=False, timeout=30.0) as response:
                if response.status_code != 200:
                    failed = True
                else:
                    raw = bytearray()
                    for part in response.iter_bytes():
                        if len(raw) + len(part) > _MAX_RESPONSE or time.monotonic() - started > 30:
                            failed = True
                            break
                        raw.extend(part)
                    if not failed:
                        parsed = _json(bytes(raw))
        except BPrepareError:
            raise
        except Exception:
            failed = True
        if failed or parsed is None:
            raise BPrepareError("http_failed")
        return parsed


def _definition(value: dict[str, Any], candidate: dict[str, Any],
                baseline_mapping_version: str) -> None:
    index = candidate["source_index"]
    if set(value) != {index}:
        raise BPrepareError("source_drift")
    details = _object(value[index])
    settings = _object(_object(details.get("settings")).get("index"))
    mapping = _object(details.get("mappings"))
    if (settings.get("uuid") != candidate["source_uuid"]
            or mapping_fingerprint(mapping) != candidate["source_mapping_sha256"]
            or _object(mapping.get("_meta")).get("mapping_version") != baseline_mapping_version
            or not _write_blocked(settings)):
        raise BPrepareError("source_drift")


def _alias(value: dict[str, Any], candidate: dict[str, Any]) -> None:
    index = candidate["source_index"]
    alias = candidate["read_alias"]
    if (set(value) != {index}
            or _object(_object(value[index]).get("aliases")).get(alias) is None
            or _sha(canonical_bytes(value)) != candidate["alias_snapshot_sha256"]):
        raise BPrepareError("source_drift")
    flags = _object(value[index]["aliases"][alias])
    if flags.get("is_write_index", False) is not False:
        raise BPrepareError("source_drift")


def _scan_rows(reader: _ScopedReader, selected: tuple[tuple[str, str, str, int], ...],
               *, model_sha: str) -> tuple[dict[str, str], ...]:
    selected_by_id = {item[0]: item for item in selected}
    counts = {item[0]: 0 for item in selected}
    seen_ids: set[str] = set()
    seen_chunks: set[str] = set()
    rows: list[dict[str, str]] = []
    after: str | None = None
    total = sum(_SELECTED_COUNTS)
    while len(rows) < total:
        request: dict[str, Any] = {
            "size": min(_PAGE, total - len(rows)), "track_total_hits": True,
            "seq_no_primary_term": True,
            "_source": ["documentId", "chunkId", "parentDocumentId", "assetId",
                        "assetVersion", "channel", "content", "title", "section",
                        "vectorRepresentationVersion", "vectorModelSnapshotSha256",
                        "vectorBodySha256", "vectorInputSha256"],
            "sort": [{"chunkId": "asc"}],
            "query": {"terms": {"assetId": list(selected_by_id)}},
        }
        if after is not None:
            request["search_after"] = [after]
        result = reader.get("POST", f"/{reader.index}/_search", request)
        shards = _object(result.get("_shards"))
        hits = _object(result.get("hits"))
        count = _object(hits.get("total"))
        entries = hits.get("hits")
        if (result.get("timed_out") is not False or shards.get("failed") != 0
                or type(shards.get("total")) is not int or shards["total"] < 1
                or shards.get("successful") != shards["total"]
                or count != {"value": total, "relation": "eq"}
                or type(entries) is not list
                or len(entries) != min(_PAGE, total - len(rows))):
            raise BPrepareError("source_record_invalid")
        for entry in entries:
            hit = _object(entry)
            fields = _object(hit.get("_source"))
            asset_id = fields.get("assetId")
            asset = selected_by_id.get(asset_id) if type(asset_id) is str else None
            identifier = hit.get("_id")
            chunk = fields.get("chunkId")
            content = fields.get("content")
            document = fields.get("documentId")
            if (asset is None or type(identifier) is not str or not identifier
                    or identifier in seen_ids or type(chunk) is not str or not chunk
                    or chunk in seen_chunks or (after is not None and chunk <= after)
                    or hit.get("_index") != reader.index or hit.get("sort") != [chunk]
                    or type(content) is not str or type(document) is not str or not document
                    or fields.get("parentDocumentId") != asset[2]
                    or fields.get("assetVersion") != asset[1]
                    or fields.get("channel") not in POLICY_CATEGORIES
                    or fields.get("vectorRepresentationVersion") != "policy-title-section-body-v1"
                    or fields.get("vectorModelSnapshotSha256") != model_sha):
                raise BPrepareError("source_record_invalid")
            invalid_representation = False
            try:
                old = build_vector_representation(content=content,
                    title=fields.get("title", ""), section=fields.get("section", ""))
                new = build_retrieval_representation_v2(body=content, kind="body-only-v2")
            except (ContractError, TypeError):
                invalid_representation = True
            if invalid_representation:
                raise BPrepareError("source_record_invalid")
            if (fields.get("vectorBodySha256") != old.content_sha256
                    or fields.get("vectorInputSha256") != old.input_sha256):
                raise BPrepareError("source_record_invalid")
            rows.append({
                "identifier": identifier, "document_id": document,
                "parent_document_id": asset[2], "asset_id": asset[0],
                "asset_version": asset[1], "version": new.version,
                "input_sha256": new.input_sha256, "body_sha256": new.body_sha256,
            })
            counts[asset[0]] += 1
            seen_ids.add(identifier)
            seen_chunks.add(chunk)
            after = chunk
    if any(counts[asset_id] != count for asset_id, _, _, count in selected):
        raise BPrepareError("source_record_invalid")
    rows.sort(key=lambda item: item["identifier"])
    return tuple(rows)


def prepare_b_intent_v1(
    *, client: httpx.Client, fixture_raw: bytes, selection_raw: bytes,
    asset_manifest_raw: bytes, preparation_raw: bytes, git_state: GitState,
    fixture_blob_reader: Callable[[str], bytes] = _git_fixture_blob,
    source_build_blob_reader: Callable[[str, str], bytes] = _git_source_build_blob,
) -> PreparedBIntent:
    """Prepare the exact pre-build intent from one seven-call scoped read."""
    try:
        preparation = _json(preparation_raw)
        if (set(preparation) != {"schemaVersion", "runId", "frozenHead", "candidate",
                                 "profileParameters", "comparisonMetadataEsHttp"}
                or preparation["schemaVersion"] != 1
                or type(preparation["runId"]) is not str
                or _RUN.fullmatch(preparation["runId"]) is None
                or type(preparation["frozenHead"]) is not str
                or type(preparation["candidate"]) is not dict
                or set(preparation["candidate"]) != _CANDIDATE_KEYS
                or type(preparation["profileParameters"]) is not dict
                or type(preparation["comparisonMetadataEsHttp"]) is not int
                or preparation["comparisonMetadataEsHttp"] != _COMPARISON_METADATA_ES_HTTP):
            raise BPrepareError("input_invalid")
        _check_git(git_state, preparation["frozenHead"])
        candidate = preparation["candidate"]
        _verify_fixture_blob(fixture_raw, preparation["frozenHead"],
                             reader=fixture_blob_reader)
        fixture = _json(fixture_raw)
        source = _object(fixture.get("sourceCorpus"))
        if (candidate["source_index"] != source.get("index")
                or candidate["source_uuid"] != source.get("indexUuid")
                or candidate["source_mapping_sha256"] != source.get("mappingSha256")
                or candidate["source_fingerprint"] != source.get("fullFingerprint")
                or candidate["source_count"] != source.get("recordCount")
                or candidate["read_alias"] != source.get("readAlias")):
            raise BPrepareError("binding_invalid")
        selected = _selected_assets(selection_raw, asset_manifest_raw)
        model = _model_binding(candidate)
        source_blobs: dict[str, bytes] = {}
        source_blob_failed = False
        try:
            source_blobs = {
                path: source_build_blob_reader(preparation["frozenHead"], path)
                for path in _SOURCE_BUILD_PATHS
            }
        except Exception:
            source_blob_failed = True
        if source_blob_failed:
            raise BPrepareError("binding_invalid")
        source_evidence = {
            "bindingPath": _SOURCE_BUILD_PATHS[0],
            "bindingSha256": _sha(source_blobs[_SOURCE_BUILD_PATHS[0]]),
            "resultPath": _SOURCE_BUILD_PATHS[1],
            "resultSha256": _sha(source_blobs[_SOURCE_BUILD_PATHS[1]]),
        }
        _verify_source_build_evidence({
            "sourceBuildEvidence": source_evidence,
            "source": {"indexName": candidate["source_index"],
                       "indexUuid": candidate["source_uuid"],
                       "sourceFingerprint": candidate["source_fingerprint"],
                       "recordCount": candidate["source_count"]},
            "modelBindings": model,
        }, preparation["frozenHead"],
            reader=lambda _head, path: source_blobs[path])
        parameters = preparation["profileParameters"]
        baseline_version = parameters["tax.policy"]["baselineMappingVersion"]
        if baseline_version != parameters["tax.law"]["baselineMappingVersion"]:
            raise BPrepareError("binding_invalid")
        budget_max = 4 + math.ceil(sum(_SELECTED_COUNTS) / _PAGE)
        reader = _ScopedReader(client, index=candidate["source_index"],
                               alias=candidate["read_alias"], maximum=budget_max)
        first_definition = reader.get("GET", f"/{reader.index}")
        first_alias = reader.get("GET", f"/_alias/{reader.alias}")
        _definition(first_definition, candidate, baseline_version)
        _alias(first_alias, candidate)
        rows = _scan_rows(reader, selected, model_sha=model["baselineModelSnapshotSha256"])
        last_definition = reader.get("GET", f"/{reader.index}")
        last_alias = reader.get("GET", f"/_alias/{reader.alias}")
        if (reader.calls != budget_max or first_definition != last_definition
                or first_alias != last_alias):
            raise BPrepareError("source_drift")
        _definition(last_definition, candidate, baseline_version)
        _alias(last_alias, candidate)
        baseline_snapshots = {
            domain: _profile_snapshot(parameters[domain]["profileId"],
                                      candidate["source_index"], candidate["source_uuid"],
                                      parameters[domain]["profileVersion"],
                                      parameters[domain]["baselineMappingVersion"])
            for domain in ("tax.policy", "tax.law")
        }
        intent = {
            "schemaVersion": 2, "kind": "knowledge_b_assessment_intent_v2",
            "uatFixtureSha256": _sha(fixture_raw),
            "source": {"indexName": candidate["source_index"],
                       "indexUuid": candidate["source_uuid"],
                       "mappingSha256": candidate["source_mapping_sha256"],
                       "sourceFingerprint": candidate["source_fingerprint"],
                       "recordCount": candidate["source_count"]},
            "candidate": {"indexName": candidate["candidate_index"],
                          "mappingSha256": candidate["target_mapping_sha256"],
                          "mappingVersion": candidate["target_mapping_version"]},
            "profileParameters": parameters,
            "baselineProfileSnapshots": baseline_snapshots,
            "builderBudget": _budget(candidate["source_count"], len(rows)),
            "mappingScanBudget": _scan_budget(candidate["source_count"]),
            "comparisonBudget": {"typedSearch": 44, "queryEmbedding": 10,
                                 "rerank": 22, "aliasWrites": 4,
                                 "metadataEsHttp": preparation["comparisonMetadataEsHttp"],
                                 "paid": 0, "retry": 0, "resume": 0},
            "representationBindings": list(rows), "modelBindings": model,
            "sourceBuildEvidence": source_evidence, "cases": _cases(fixture),
            "thresholds": _THRESHOLDS,
        }
        intent_raw = canonical_bytes(intent)
        _intent(intent_raw, fixture_raw)
        preliminary = {
            "schemaVersion": 2, "runId": preparation["runId"],
            "frozenHead": preparation["frozenHead"],
            "assessmentIntentSha256": _sha(intent_raw), "candidate": candidate,
            "representationBindings": list(rows),
            "budget": intent["builderBudget"],
            "mappingScanBudget": intent["mappingScanBudget"],
        }
        return PreparedBIntent(intent_raw, canonical_bytes(preliminary), rows,
                               reader.calls, budget_max,
                               (source_evidence["bindingSha256"],
                                source_evidence["resultSha256"]))
    except (BFreezeError, ContractError, KeyError, TypeError, ValueError, IndexError):
        pass
    raise BPrepareError("binding_invalid")


def bind_b_request_v1(*, preliminary_raw: bytes, source_id_mapping_raw: bytes) -> bytes:
    """Bind the later full-source mapping without an invented placeholder hash."""
    preliminary = _json(preliminary_raw)
    if (set(preliminary) != {"schemaVersion", "runId", "frozenHead",
                             "assessmentIntentSha256", "candidate",
                             "representationBindings", "budget", "mappingScanBudget"}
            or preliminary["schemaVersion"] != 2):
        raise BPrepareError("input_invalid")
    candidate = _object(preliminary["candidate"])
    try:
        _id_mapping(source_id_mapping_raw,
                    source_index=candidate["source_index"],
                    source_uuid=candidate["source_uuid"],
                    source_fingerprint=candidate["source_fingerprint"],
                    source_count=candidate["source_count"])
    except (BFreezeError, KeyError, TypeError, ValueError):
        pass
    else:
        return canonical_bytes({**preliminary, "idMappingSha256": _sha(source_id_mapping_raw)})
    raise BPrepareError("binding_invalid")
