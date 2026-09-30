"""Read-only human-label handoff for a completed comparison-only B reuse run.

This replays the frozen comparison and checks its persisted finite terminal. It
does not independently reconstruct the owned Java/ES processes or certify that
the self-declared reviewer is human. No source body, network, or model is read.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, cast

from tests.evaluation.knowledge import rebuild_b_reuse_binding as reuse
from tests.evaluation.knowledge.rebuild_b_comparator import (
    ArmTrace, CallTotals, CandidateRef, CaseTrace, ComparisonRun, ComparisonRunError,
    ComparisonSpec, FrozenIdMapping, StageRanks, _canonical_bytes,
    _sidecar, blind_label_pool, comparison_spec_fingerprint, score_comparison,
)
from tests.evaluation.knowledge.rebuild_b_local_runner import (
    _validate_profile_parameters,
)


EVIDENCE_ROOT = Path(__file__).resolve().parents[4] / "knowledge-corpus-tools/evidence"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_EMPTY_SHA256 = sha256(b"").hexdigest()
_REVIEW_CONFIRMATION = "maintainer_personally_reviewed_each_supplied_label_against_source_text"
_SIDE_FILES = {
    "reuseIntent": "reuse-intent.json", "reuseFinal": "reuse-final.json",
    "reuseAttempt": "reuse-scan-attempt.json", "reuseTerminal": "reuse-scan-terminal.json",
    "sourceScanResult": "source-scan-result.json",
    "candidateScanResult": "candidate-scan-result.json",
}


class ReviewError(ValueError):
    """Finite, content-free rejection of an unscorable review input."""

    def __init__(self) -> None:
        super().__init__("review_input_invalid")


def _require(condition: bool) -> None:
    if not condition:
        raise ReviewError()


def _read(path: Path, *, maximum: int = 2 * 1024 * 1024) -> bytes:
    try:
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
    except OSError:
        raise ReviewError() from None
    _require(bool(raw) and len(raw) <= maximum)
    return raw


def _json(raw: bytes) -> dict[str, Any]:
    try:
        return _sidecar(raw)
    except (ComparisonRunError, ValueError, TypeError, UnicodeError):
        raise ReviewError() from None


def _hash(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def _frozen_spec(directory: Path) -> tuple[ComparisonSpec, dict[str, bytes], reuse.OldBuild]:
    """Rebind immutable old Git blobs and new local v2 scans, without execution admission."""
    _require(directory.parent == EVIDENCE_ROOT.resolve())
    sidecars = {key: _read(directory / name) for key, name in _SIDE_FILES.items()}
    intent = _json(sidecars["reuseIntent"])
    _require(intent.get("runId") == directory.name and intent.get("branch") == "codex_0915")
    old = reuse.load_old_build()
    head = intent.get("frozenHead")
    if not isinstance(head, str) or re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise ReviewError()
    fixture = reuse.git_blob(head, reuse.FIXTURE_PATH)
    expected = reuse.freeze_new_reuse_input(
        old=old, run_id=directory.name, frozen_head=head,
        profile_parameters=intent["profileParameters"],
        config_raw=reuse.git_blob(head, reuse.CONFIG_PATH), fixture_raw=fixture)
    _require(expected == sidecars["reuseIntent"])
    _validate_profile_parameters(head, intent["profileParameters"])
    maps = {arm: _read(directory / f"{arm}-id-mapping.json", maximum=16 * 1024 * 1024)
            for arm in ("source", "candidate")}
    final = _json(sidecars["reuseFinal"])
    for arm, original in (("source", old.source_map), ("candidate", old.candidate_map)):
        mapping = FrozenIdMapping.from_bytes(maps[arm], expected_sha256=_hash(maps[arm]))
        _require(mapping == original)
        version = intent["profileParameters"]["tax.policy"][
            "baselineMappingVersion" if arm == "source" else "candidateMappingVersion"]
        receipt = reuse.scan_receipt(arm=arm, intent_raw=expected, map_raw=maps[arm],
            es_http=64, mapping_version=version, execution_kind="local")
        _require(receipt == sidecars[f"{arm}ScanResult"])
        _require(final[f"{arm}IdMappingSha256"] == _hash(maps[arm]))
    expected_final = reuse.finalize_reuse_scans(intent_raw=expected,
        source_scan_raw=sidecars["sourceScanResult"],
        candidate_scan_raw=sidecars["candidateScanResult"],
        source_map_raw=maps["source"], candidate_map_raw=maps["candidate"])
    _require(expected_final == sidecars["reuseFinal"])
    reuse.verify_reuse_scan_execution(intent_raw=expected, final_raw=expected_final,
        attempt_raw=sidecars["reuseAttempt"], terminal_raw=sidecars["reuseTerminal"])
    return reuse.spec_for_reuse(old, intent_raw=expected, final_raw=expected_final), sidecars, old


def _ref(raw: object) -> CandidateRef:
    _require(type(raw) is dict and set(raw) == {"document_id", "chunk_id", "content_sha256"})
    item = cast(dict[str, Any], raw)
    return CandidateRef(item["document_id"], item["chunk_id"], item["content_sha256"])


def _pairs(raw: object) -> tuple[tuple[str, Any], ...]:
    _require(type(raw) is list and all(type(item) is list and len(item) == 2
                                       and type(item[0]) is str for item in raw))
    return tuple((item[0], item[1]) for item in cast(list[list[Any]], raw))


def _stage(raw: object) -> StageRanks:
    _require(type(raw) is dict and set(raw) == {"domain_id", "path", "ranked"}
             and type(raw["domain_id"]) is str and type(raw["path"]) is str
             and type(raw["ranked"]) is list)
    item = cast(dict[str, Any], raw)
    return StageRanks(item["domain_id"], item["path"], tuple(_ref(ref) for ref in item["ranked"]))


def _arm(raw: object, expected: str) -> ArmTrace:
    _require(type(raw) is dict and set(raw) == {"arm", "keyword", "keyword_es_ids",
        "vector", "fused", "reranked", "final20", "read_policy_by_domain", "latency_seconds"}
        and raw["arm"] == expected and type(raw["latency_seconds"]) in (int, float))
    item = cast(dict[str, Any], raw)
    for key in ("keyword", "vector", "fused", "reranked", "final20"):
        _require(type(item[key]) is list)
    es_ids = _pairs(item["keyword_es_ids"])
    policies = _pairs(item["read_policy_by_domain"])
    _require(all(type(ids) is list and all(type(value) is str for value in ids)
                 for _, ids in es_ids)
             and all(type(value) is str for _, value in policies))
    return ArmTrace(expected, tuple(_stage(stage) for stage in item["keyword"]),
        tuple((domain, tuple(ids)) for domain, ids in es_ids),
        tuple(_stage(stage) for stage in item["vector"]),
        tuple(_ref(ref) for ref in item["fused"]),
        tuple(_stage(stage) for stage in item["reranked"]),
        tuple(_ref(ref) for ref in item["final20"]),
        tuple((domain, value) for domain, value in policies),
        float(item["latency_seconds"]))


def _traces(raw: object, spec: ComparisonSpec) -> tuple[CaseTrace, ...]:
    _require(type(raw) is list and len(raw) == len(spec.cases))
    traces: list[CaseTrace] = []
    for item, case in zip(cast(list[Any], raw), spec.cases, strict=True):
        _require(type(item) is dict and set(item) == {"case_id", "baseline", "candidate"}
                 and item["case_id"] == case.case_id)
        baseline = _arm(item["baseline"], "baseline")
        candidate = _arm(item["candidate"], "candidate")
        traces.append(CaseTrace(case.case_id, baseline, candidate))
    return tuple(traces)


def _completed_run(spec: ComparisonSpec, old: reuse.OldBuild, attempt: dict[str, Any],
                   terminal: dict[str, Any], *, frozen_head: str) -> ComparisonRun:
    _require(set(attempt) == {"schemaVersion", "status", "runId", "frozenHead",
        "assessmentSha256", "javaArtifactSha256", "aliases", "budget"}
        and attempt["schemaVersion"] == 1 and attempt["status"] == "consumed"
        and attempt["runId"] == terminal.get("runId")
        and attempt["frozenHead"] == frozen_head
        and terminal.get("frozenHead") == frozen_head
        and attempt["assessmentSha256"] == spec.assessment_sha256
        and type(attempt["javaArtifactSha256"]) is str
        and _SHA.fullmatch(attempt["javaArtifactSha256"]) is not None
        and attempt["budget"] == {"typedSearch": 44, "queryEmbedding": 10,
            "rerank": 22, "metadataEsHttp": 30, "aliasWrites": 4,
            "paid": 0, "retry": 0, "resume": 0})
    aliases = attempt["aliases"]
    _require(type(aliases) is list and len(aliases) == 2 and len(set(aliases)) == 2
        and all(type(alias) is str and re.fullmatch(
            rf"b-{re.escape(attempt['runId'])}-[0-9a-f]{{16,32}}-read", alias)
            for alias in aliases))
    _require(set(terminal) == {"schemaVersion", "runId", "frozenHead", "status",
        "evidenceKind", "assessmentSha256", "uatFixtureSha256", "provenanceSha256",
        "comparisonSpecSha256", "calls", "aliasWrites", "metadataEsHttp", "ownedPids",
        "ownedProcessesStopped", "aliasesRemoved", "proxyViolations", "paid", "retry",
        "resume", "witness", "traces", "modelIdentityPre", "modelIdentityPost"}
        and terminal["schemaVersion"] == 1
        and terminal["status"] == "completed_awaiting_blind_labels"
        and terminal["evidenceKind"] == "local_verified"
        and terminal["assessmentSha256"] == spec.assessment_sha256
        and terminal["uatFixtureSha256"] == spec.uat_fixture_sha256
        and terminal["comparisonSpecSha256"] == comparison_spec_fingerprint(spec)
        and type(terminal["provenanceSha256"]) is str
        and _SHA.fullmatch(terminal["provenanceSha256"]) is not None
        and terminal["aliasWrites"] == 4 and terminal["metadataEsHttp"] == 30
        and terminal["ownedProcessesStopped"] is True
        and terminal["aliasesRemoved"] is True and terminal["proxyViolations"] == 0
        and all(terminal[key] == 0 for key in ("paid", "retry", "resume")))
    pids = terminal["ownedPids"]
    _require(type(pids) is list and len(pids) == 2 and len(set(pids)) == 2
             and all(type(pid) is int and pid > 0 for pid in pids))
    calls = terminal["calls"]
    _require(type(calls) is dict and set(calls) == {"typed_search", "query_embedding", "online_rerank"}
        and type(calls["typed_search"]) is int and calls["typed_search"] == 44
        and type(calls["query_embedding"]) is int and calls["query_embedding"] == 10
        and type(calls["online_rerank"]) is int and 0 <= calls["online_rerank"] <= 22)
    pre, post = terminal["modelIdentityPre"], terminal["modelIdentityPost"]
    _require(type(pre) is dict and pre == post and set(pre) == {"schemaVersion", "embedding",
        "rerank", "sha256"} and pre["schemaVersion"] == 1
        and type(pre["sha256"]) is str and pre["sha256"] == _hash(_canonical_bytes({
            "embedding": pre["embedding"], "rerank": pre["rerank"]})))
    old_model = _json(dict(old.blobs)["binding.json"])["spec"]["model_snapshot"]
    _require(type(pre["embedding"]) is dict and type(pre["rerank"]) is dict
        and pre["embedding"].get("model") == old_model["model"]
        and type(pre["embedding"].get("container")) is dict
        and {key: value for key, value in pre["embedding"]["container"].items()
             if key != "started"} == {key: value for key, value in old_model["container"].items()
                                     if key != "started"})
    witness = terminal["witness"]
    _require(type(witness) is dict and set(witness) == {"baseline", "candidate"})
    canonical_request_hashes: list[list[str]] = []
    for arm, alias, corpus in zip(("baseline", "candidate"), aliases,
                                  (spec.source_corpus, spec.candidate_corpus), strict=True):
        rows = witness[arm]
        _require(type(rows) is list and len(rows) == 6 + 22)
        allowed_get = {f"/_alias/{alias}", f"/{corpus.index_name}/_settings",
                       f"/{corpus.index_name}/_mapping"}
        post_canonical_hashes: list[str] = []
        gets = 0
        for row in rows:
            _require(type(row) is dict and set(row) == {"method", "path", "request_sha256",
                "canonical_request_sha256", "status"}
                and type(row["request_sha256"]) is str
                and _SHA.fullmatch(row["request_sha256"]) is not None
                and type(row["canonical_request_sha256"]) is str
                and _SHA.fullmatch(row["canonical_request_sha256"]) is not None
                and type(row["status"]) is int and row["status"] == 200)
            if row["method"] == "GET":
                _require(row["path"] in allowed_get
                    and row["request_sha256"] == _EMPTY_SHA256
                    and row["canonical_request_sha256"] == _EMPTY_SHA256)
                gets += 1
            else:
                _require(row["method"] == "POST" and row["path"] == f"/{corpus.index_name}/_search")
                post_canonical_hashes.append(row["canonical_request_sha256"])
        _require(gets == 6 and len(post_canonical_hashes) == 22)
        canonical_request_hashes.append(post_canonical_hashes)
    _require(Counter(canonical_request_hashes[0]) == Counter(canonical_request_hashes[1]))
    traces = _traces(terminal["traces"], spec)
    return ComparisonRun(traces, CallTotals(calls["typed_search"], calls["query_embedding"],
        calls["online_rerank"]), spec.assessment_sha256, spec.uat_fixture_sha256,
        terminal["provenanceSha256"], comparison_spec_fingerprint(spec), "local_verified")


def _labels(raw: bytes, *, run_id: str, result_sha: str, pool_sha: str,
            pool: tuple[tuple[str, str, str, str], ...]) -> tuple[dict[tuple[str, str, str, str], bool], str]:
    value = _json(raw)
    _require(set(value) == {"schemaVersion", "runId", "comparisonResultSha256",
        "blindPoolSha256", "reviewerId", "confirmation", "items"}
        and value["schemaVersion"] == 1 and value["runId"] == run_id
        and value["comparisonResultSha256"] == result_sha
        and value["blindPoolSha256"] == pool_sha
        and type(value["reviewerId"]) is str
        and re.fullmatch(r"[A-Za-z0-9._-]{3,64}", value["reviewerId"]) is not None
        and value["confirmation"] == _REVIEW_CONFIRMATION
        and type(value["items"]) is list)
    judged: dict[tuple[str, str, str, str], bool] = {}
    for item in value["items"]:
        _require(type(item) is dict and set(item) == {"caseId", "documentId", "chunkId",
            "contentSha256", "directlyRelevant"} and type(item["directlyRelevant"]) is bool)
        key = (item["caseId"], item["documentId"], item["chunkId"], item["contentSha256"])
        _require(key in pool and key not in judged)
        judged[key] = item["directlyRelevant"]
    return judged, value["reviewerId"]


def review(directory: Path, *, labels_raw: bytes | None) -> dict[str, object]:
    """Return a blank blind template or bounded metrics; never write an asset."""
    directory = directory.resolve()
    try:
        spec, sidecars, old = _frozen_spec(directory)
        attempt = _json(_read(directory / "comparison-attempt.json"))
        result_raw = _read(directory / "comparison-result.json")
        terminal = _json(result_raw)
        attestation = _json(_read(directory / "comparison-java-attestation.json"))
        frozen_head = _json(sidecars["reuseIntent"])["frozenHead"]
        _require(attestation.get("runId") == directory.name
                 and attestation.get("frozenHead") == frozen_head
                 and attestation.get("artifactSha256") == attempt.get("javaArtifactSha256")
                 and attestation.get("buildExitCode") == 0
                 and attestation.get("workingTreeTrackedClean") is True)
        _require(attempt.get("runId") == directory.name
                 and terminal.get("frozenHead") == frozen_head)
        run = _completed_run(spec, old, attempt, terminal, frozen_head=frozen_head)
        pool_raw = _read(directory / "comparison-blind-label-pool.json")
        saved_pool = _json(pool_raw)
        pool = blind_label_pool(run)
        _require(set(saved_pool) == {"schemaVersion", "runId", "armHidden", "items"}
            and saved_pool["schemaVersion"] == 1 and saved_pool["runId"] == directory.name
            and saved_pool["armHidden"] is True
            and saved_pool["items"] == [list(key) for key in pool])
        result_sha, pool_sha = _hash(result_raw), _hash(pool_raw)
        if labels_raw is None:
            return {"schemaVersion": 1, "runId": directory.name,
                "comparisonResultSha256": result_sha, "blindPoolSha256": pool_sha,
                "reviewerId": None, "confirmation": None,
                "items": [{"caseId": key[0], "documentId": key[1], "chunkId": key[2],
                           "contentSha256": key[3], "directlyRelevant": None} for key in pool]}
        labels, reviewer = _labels(labels_raw, run_id=directory.name, result_sha=result_sha,
                                   pool_sha=pool_sha, pool=pool)
        metrics = score_comparison(spec=spec, run=run, labels=labels)
        return {"schemaVersion": 1, "runId": directory.name,
            "comparisonResultSha256": result_sha, "blindPoolSha256": pool_sha,
            "reviewerId": reviewer, "reviewerSelfAttested": True,
            "humanIdentityIndependentlyVerified": False,
            "runtimeProvenanceIndependentlyReconstructed": False,
            "outcome": metrics.outcome, "reasons": list(metrics.reasons),
            "labelPoolSize": metrics.label_pool_size, "unjudgedCount": metrics.unjudged_count,
            "macroBaselineRecall": metrics.macro_baseline_recall,
            "macroCandidateRecall": metrics.macro_candidate_recall,
            "macroBaselinePrecision": metrics.macro_baseline_precision,
            "macroCandidatePrecision": metrics.macro_candidate_precision,
            "medianBaselineLatency": metrics.median_baseline_latency,
            "medianCandidateLatency": metrics.median_candidate_latency,
            "caseMetrics": [asdict(item) for item in metrics.case_metrics]}
    except (ReviewError, reuse.ReuseBindingError, ComparisonRunError, ValueError, TypeError, KeyError,
            UnicodeError, OSError, AttributeError, StopIteration):
        raise ReviewError() from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--blank-template", action="store_true")
    choice.add_argument("--labels", type=Path)
    args = parser.parse_args()
    try:
        raw = None if args.blank_template else _read(args.labels)
        output = review(args.run_directory, labels_raw=raw)
    except ReviewError:
        print(json.dumps({"status": "not_assessed", "reason": "review_input_invalid"},
                         sort_keys=True))
        return 1
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
