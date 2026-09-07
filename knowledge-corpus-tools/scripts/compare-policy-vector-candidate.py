"""Read-only same-window ANN/keyword diagnostic, not typed UAT or publication."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx

from knowledge_corpus_tools.jsonio import exclusive_write
from knowledge_corpus_tools.local_vector_preparation import LocalVectorPreparation
from knowledge_corpus_tools.vector_candidate import (
    MAPPING_VERSION, POLICY_CATEGORIES, VectorCandidateSpec, _Build, canonical_bytes,
)
from knowledge_corpus_tools.vector_representation import build_vector_representation

QUESTIONS = (
    "住宿服务生活服务",
    "增值税政策中，生活服务中的住宿服务如何定义？",
    "住宿服务与不动产租赁的增值税分类有什么区别？",
    "2016年一般纳税人按一般计税提供住宿服务的增值税税率是多少？",
    "财税〔2011〕100号规定软件产品享受增值税即征即退需取得哪些证明材料？",
)


def search_body(question: str, vector: tuple[float, ...], path: str) -> dict[str, Any]:
    category = {"terms": {"channel": sorted(POLICY_CATEGORIES)}}
    body: dict[str, Any] = {"_source": ["chunkId"], "size": 21, "track_total_hits": False}
    if path == "vector":
        body["knn"] = {"field": "embedding", "query_vector": vector, "k": 21,
                       "num_candidates": 100, "filter": category}
    elif path == "keyword":
        body["query"] = {"bool": {"filter": [category], "must": [{"multi_match": {
            "query": question, "fields": ["title", "content", "section"]}}]}}
    else:
        raise ValueError("path_invalid")
    return body


def main() -> None:
    # This offline diagnostic uses assertions for its frozen execution checks.
    # Never allow an optimized interpreter to silently remove those checks.
    if not __debug__:
        raise RuntimeError("optimized_interpreter_not_supported")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    directory: Path = args.directory
    destination = directory / "ann-comparison.json"
    if destination.exists():
        raise ValueError("comparison_exists")
    binding_raw = (directory / "binding.json").read_bytes()
    binding = json.loads(binding_raw)
    result_raw = (directory / "result.json").read_bytes()
    result = json.loads(result_raw)
    assert result["status"] == "built_read_only_unpublished"
    assert result["bindingSha256"] == hashlib.sha256(binding_raw).hexdigest()
    spec = VectorCandidateSpec(**binding["spec"])
    gold_path = Path(__file__).resolve().parents[1] / "evidence/vector-representation-full-policy-20260907.v1.json"
    gold_raw = gold_path.read_bytes()
    gold = json.loads(gold_raw)
    prep = LocalVectorPreparation(binding["modelSnapshot"]["container"]["id"])
    prep.freeze()
    assert prep.snapshot_sha256 == spec.model_snapshot_sha256
    rows = []
    with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                      transport=httpx.HTTPTransport(retries=0)) as client:
        check = _Build(spec, client)
        source = check.source()
        candidate = check.definition(spec.candidate_index)
        settings = candidate["settings"]["index"]
        assert settings["uuid"] == result["result"]["candidate_uuid"]
        assert settings["blocks"]["write"] == "true" and candidate["aliases"] == {}
        assert candidate["mappings"]["_meta"]["mapping_version"] == MAPPING_VERSION
        vectors = prep(tuple(build_vector_representation(content=q) for q in QUESTIONS))
        for i, (question, vector) in enumerate(zip(QUESTIONS, vectors, strict=True)):
            expected = gold["results"][i]["required"]
            row: dict[str, Any] = {"queryOrdinal": i + 1, "required": expected,
                                   "questionSha256": hashlib.sha256(question.encode()).hexdigest()}
            for label, index in (("source", spec.source_index), ("candidate", spec.candidate_index)):
                paths = {}
                for path in ("keyword", "vector"):
                    response = check.request("POST", f"/{index}/_search", body=search_body(question, vector, path))
                    assert response is not None and response["timed_out"] is False
                    assert response["_shards"]["failed"] == 0
                    assert response["_shards"]["successful"] == response["_shards"]["total"]
                    hits = response["hits"]["hits"]
                    assert len(hits) <= 21 and all(h["_index"] == index for h in hits)
                    ids = [h["_source"]["chunkId"] for h in hits[:20]]
                    assert len(ids) == len(set(ids))
                    paths[path] = [ids.index(gold["goldChunkIds"][name]) + 1
                                   if gold["goldChunkIds"][name] in ids else None for name in expected]
                row[label] = paths
            rows.append(row)
        assert check.source() == source and check.definition(spec.candidate_index) == candidate
        finite = {"schemaVersion": 1, "kind": "same_window_read_only_candidate_comparison",
                  "bindingSha256": hashlib.sha256(binding_raw).hexdigest(),
                  "buildResultSha256": hashlib.sha256(result_raw).hexdigest(),
                  "goldAuthoritySha256": hashlib.sha256(gold_raw).hexdigest(),
                  "modelSnapshotSha256": prep.snapshot_sha256, "results": rows,
                  "esReadHttp": check.calls, "embeddingHttp": prep.http_calls,
                  "embeddingTexts": prep.text_count, "maxTokens": prep.max_tokens,
                  "paid": 0, "esWrites": 0, "aliasWrites": 0, "retry": 0,
                  "window": 20, "numCandidates": 100,
                  "limitations": ["not_typed_authorization_test", "not_rerank_or_summary",
                                  "not_full_uat", "no_alias_publication"]}
    exclusive_write(destination, canonical_bytes(finite))
    print(json.dumps(finite, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    code = 1
    try:
        main()
        code = 0
    except Exception:
        print('{"status":"failed","reason":"comparison_failed_no_retry"}')
    raise SystemExit(code)
