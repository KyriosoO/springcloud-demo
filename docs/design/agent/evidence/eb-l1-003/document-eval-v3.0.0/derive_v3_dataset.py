#!/usr/bin/env python3
"""Deterministically derive the frozen v3 corpus and cases from v2.

This script is provenance tooling, not part of evaluation execution. Running it
rewrites corpus.jsonl and evaluation_cases.jsonl; SHA256SUMS must then be
regenerated before the package is frozen again.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PACK_DIR = Path(__file__).resolve().parent
SOURCE_DIR = PACK_DIR.parent / "document-eval-v2.0.0"
CORPUS_ID = "document-default"
DOMAIN = "default_document_corpus"
CLASSIFICATION = "internal"
POLICY_VERSION = "document-corpus-policy-2026-07-17.1"
PERMISSION_CODE = "DOCUMENT_CORPUS_READ"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "\n".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    )
    path.write_text(content + "\n", encoding="utf-8", newline="\n")


def transform_chunk(source: dict[str, Any]) -> dict[str, Any]:
    chunk: dict[str, Any] = {
        "chunk_id": source["chunk_id"],
        "document_id": source["document_id"],
        "version": source["version"],
        "corpus_id": CORPUS_ID,
        "domain": DOMAIN,
        "title": source["title"],
        "status": source["status"],
        "valid_from": source["valid_from"],
        "valid_to": source["valid_to"],
        "classification": CLASSIFICATION,
    }
    for optional in ("superseded_by", "supersedes", "revoked_at"):
        if optional in source:
            chunk[optional] = source[optional]
    chunk["synthetic"] = True
    chunk["content"] = source["content"]
    return chunk


def distractor_chunks() -> list[dict[str, Any]]:
    topics = [
        "差旅", "休假", "远程办公", "结算", "退款", "审批", "文档安全", "培训", "设备", "采购",
        "会议", "访客", "报销", "档案", "值班", "通知", "预算", "合同", "印章", "资产",
    ]
    rows: list[dict[str, Any]] = []
    for index in range(1, 55):
        topic = topics[(index - 1) % len(topics)]
        identifier = f"DOC-DISTRACTOR-{index:03d}"
        rows.append(
            {
                "chunk_id": f"{identifier}#C01",
                "document_id": identifier,
                "version": "1.0",
                "corpus_id": CORPUS_ID,
                "domain": DOMAIN,
                "title": f"{topic}流程参考条目 {index:03d}",
                "status": "active",
                "valid_from": "2024-01-01",
                "valid_to": None,
                "classification": CLASSIFICATION,
                "synthetic": True,
                "content": (
                    f"模拟{topic}干扰条目 {index:03d}。本条仅用于扩展 Recall@50 有效候选池，"
                    f"识别码为 DIST-{index:03d}；不包含任何评价问题的标准答案或真实业务信息。"
                ),
            }
        )
    return rows


def default_subject(subject_id: str) -> dict[str, Any]:
    return {
        "subject_id": subject_id,
        "rbac_authorized": True,
        "document_capability_authorized": True,
        "corpus_permissions": [PERMISSION_CODE],
        "corpus_permission_state": "active",
    }


def default_access_context() -> dict[str, Any]:
    return {
        "corpus_id": CORPUS_ID,
        "corpus_enabled": True,
        "required_policy_version": POLICY_VERSION,
        "observed_policy_version": POLICY_VERSION,
        "required_fence_version": 1,
        "observed_fence_version": 1,
    }


def transform_case(source: dict[str, Any]) -> dict[str, Any]:
    case = dict(source)
    case["domain"] = DOMAIN
    case["subject"] = default_subject(source["subject"]["subject_id"])
    case["access_context"] = default_access_context()

    if source["case_id"] == "DOC-EVAL-018":
        case["subject"]["rbac_authorized"] = False
        case["tags"] = sorted(set(case["tags"] + ["rbac_denied", "zero_candidate_required"]))
    elif source["case_id"] == "DOC-EVAL-019":
        case["subject"]["document_capability_authorized"] = False
        case["tags"] = sorted(set(case["tags"] + ["document_capability_denied", "zero_candidate_required"]))
    elif source["case_id"] == "DOC-EVAL-026":
        case["subject"]["corpus_permissions"] = []
        case["tags"] = sorted(set(case["tags"] + ["corpus_permission_denied", "zero_candidate_required"]))
    return case


def refusal_case(
    case_id: str,
    scenario: str,
    subject_id: str,
    question: str,
    refusal_reason: str,
    reference_answer: str,
    forbidden_chunk: str,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "scenario": scenario,
        "domain": DOMAIN,
        "subject": default_subject(subject_id),
        "access_context": default_access_context(),
        "as_of": "2026-07-17",
        "conversation_id": None,
        "turn": 1,
        "question": question,
        "answerability": "refuse",
        "refusal_reason": refusal_reason,
        "relevant_chunks": [],
        "required_points": [
            {
                "point_id": "P1",
                "text": reference_answer,
                "supporting_chunks": [],
            }
        ],
        "reference_answer": reference_answer,
        "allowed_citations": [],
        "forbidden_citations": [forbidden_chunk],
        "tags": sorted(set(["should_refuse", "zero_candidate_required", *tags])),
    }


def new_security_cases() -> list[dict[str, Any]]:
    disabled = refusal_case(
        "DOC-EVAL-027",
        "corpus_disabled",
        "S-EMP-DISABLED",
        "语料库停用后还能查询员工年休假规则吗？",
        "corpus_disabled",
        "语料库已停用，必须在检索前失败关闭，不能返回任何候选。",
        "EMP-LEAVE-2026#C01",
        ["corpus_disabled", "fail_closed"],
    )
    disabled["access_context"]["corpus_enabled"] = False
    disabled["access_context"]["required_fence_version"] = 2
    disabled["access_context"]["observed_fence_version"] = 2

    revoked = refusal_case(
        "DOC-EVAL-028",
        "access_revoked",
        "S-EMP-REVOKED",
        "我的语料库权限已撤销，还能查询北京差旅住宿上限吗？",
        "access_revoked",
        "语料库访问权限已撤销且围栏已生效，必须返回零候选。",
        "EMP-TRAVEL-2026#C01",
        ["access_revoked", "revocation_fence"],
    )
    revoked["subject"]["corpus_permission_state"] = "revoked"
    revoked["access_context"]["required_fence_version"] = 3
    revoked["access_context"]["observed_fence_version"] = 3

    stale_fence = refusal_case(
        "DOC-EVAL-029",
        "revocation_fence",
        "S-EMP-FENCE",
        "撤权围栏尚未在检索节点可见时可以继续查询吗？",
        "revocation_fence_stale",
        "撤权围栏版本尚未全局可见，查询必须失败关闭并返回零候选。",
        "EMP-TRAVEL-2026#C01",
        ["revocation_fence", "stale_fence", "fail_closed"],
    )
    stale_fence["access_context"]["required_fence_version"] = 4
    stale_fence["access_context"]["observed_fence_version"] = 3

    policy_mismatch = refusal_case(
        "DOC-EVAL-030",
        "policy_version",
        "S-EMP-POLICY",
        "检索节点仍使用旧权限策略版本时可以返回候选吗？",
        "policy_version_mismatch",
        "权限策略版本不一致，查询必须失败关闭并返回零候选。",
        "EMP-TRAVEL-2026#C01",
        ["policy_version_mismatch", "fail_closed"],
    )
    policy_mismatch["access_context"]["observed_policy_version"] = (
        "document-corpus-policy-2026-07-16.9"
    )
    return [disabled, revoked, stale_fence, policy_mismatch]


def main() -> None:
    source_corpus = load_jsonl(SOURCE_DIR / "corpus.jsonl")
    source_cases = load_jsonl(SOURCE_DIR / "evaluation_cases.jsonl")
    corpus = [transform_chunk(row) for row in source_corpus] + distractor_chunks()
    cases = [transform_case(row) for row in source_cases] + new_security_cases()
    write_jsonl(PACK_DIR / "corpus.jsonl", corpus)
    write_jsonl(PACK_DIR / "evaluation_cases.jsonl", cases)
    print(
        json.dumps(
            {"corpus_chunks": len(corpus), "evaluation_cases": len(cases)},
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
