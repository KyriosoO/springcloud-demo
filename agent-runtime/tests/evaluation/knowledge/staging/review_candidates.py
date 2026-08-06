from __future__ import annotations

import argparse
import asyncio
import json
import unicodedata
from pathlib import Path
from typing import Any

from agent_runtime.knowledge.contracts import RetrievalStageKind
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import RankedKnowledgeBatch
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.evaluation.knowledge.staging.collect_candidate_retrieval import (
    _context,
    _evidence_id,
    _plan,
    _required,
)
from tests.evaluation.knowledge.staging.validate_candidate_package import read_jsonl


_MAX_CASES_PER_INVOCATION = 26
_MAX_DISPLAY_CANDIDATES = 10
_MAX_SNIPPET_CODE_POINTS = 240


def _snippet(value: str, *, focus_tokens: tuple[str, ...]) -> tuple[str, bool, str | None]:
    normalized = unicodedata.normalize("NFC", " ".join(value.split()))
    boundary_tokens = tuple(
        token for token in focus_tokens if any(character.isdigit() for character in token) or "条" in token or "号" in token
    )
    ordered_tokens = boundary_tokens + tuple(token for token in focus_tokens if token not in boundary_tokens)
    focus_token = next((token for token in ordered_tokens if token in normalized), None)
    focus_index = normalized.find(focus_token) if focus_token is not None else 0
    start = max(0, focus_index - 40)
    end = min(len(normalized), start + _MAX_SNIPPET_CODE_POINTS)
    return normalized[start:end], start > 0 or end < len(normalized), focus_token


def _build_transient_view(
    *,
    candidate: dict[str, Any],
    batch: RankedKnowledgeBatch,
    display_limit: int,
) -> dict[str, object]:
    documents: list[dict[str, object]] = []
    focus_tokens = tuple(str(value) for value in candidate["must_preserve_tokens"])
    for item in batch.candidates[:display_limit]:
        source = item.candidate
        snippet, truncated, focus_token = _snippet(source.content, focus_tokens=focus_tokens)
        documents.append(
            {
                "rank": item.rank,
                "document_id": source.document_id,
                "evidence_id": _evidence_id(source),
                "domain_ids": list(item.domain_ids),
                "title": source.title,
                "document_number": source.document_number,
                "written_date": source.written_date.isoformat() if source.written_date is not None else None,
                "material_type": source.material_type,
                "snippet": snippet,
                "snippet_truncated": truncated,
                "snippet_focus_token": focus_token,
            }
        )
    return {
        "status": "transient_maintainer_review_only",
        "candidate_id": candidate["candidate_id"],
        "question": candidate["question"],
        "proposed_category": candidate["proposed_category"],
        "proposed_expected_domain_ids": candidate["proposed_expected_domain_ids"],
        "proposed_expected_answerability": candidate["proposed_expected_answerability"],
        "candidate_documents": documents,
        "persistence_allowed": False,
        "maintainer_confirmation": "pending",
    }


def _verify_annotation(
    *,
    candidate_id: str,
    batch: RankedKnowledgeBatch,
    annotation: dict[str, Any],
) -> None:
    expected_documents = annotation["candidate_documents"]
    actual_documents = [
        {
            "rank": item.rank,
            "document_id": item.candidate.document_id,
            "evidence_id": _evidence_id(item.candidate),
            "domain_ids": list(item.domain_ids),
        }
        for item in batch.candidates
    ]
    if annotation["retrieval_status"] != "retrieved" or actual_documents != expected_documents:
        raise RuntimeError(f"candidate_review.annotation_drift:{candidate_id}")
    if list(batch.index_snapshot_ids) != annotation["index_snapshot_ids"]:
        raise RuntimeError(f"candidate_review.snapshot_drift:{candidate_id}")
    if batch.profile_version != annotation["retrieval_profile_version"]:
        raise RuntimeError(f"candidate_review.profile_drift:{candidate_id}")


def _selected_candidates(
    *,
    candidates: tuple[dict[str, Any], ...],
    case_ids: list[str],
) -> tuple[dict[str, Any], ...]:
    if not case_ids or len(case_ids) > _MAX_CASES_PER_INVOCATION or len(set(case_ids)) != len(case_ids):
        raise RuntimeError("candidate_review.invalid_case_selection")
    by_id = {str(candidate["candidate_id"]): candidate for candidate in candidates}
    if any(case_id not in by_id for case_id in case_ids):
        raise RuntimeError("candidate_review.unknown_case")
    return tuple(by_id[case_id] for case_id in case_ids)


async def _review(
    *,
    questions_path: Path,
    annotations_path: Path,
    case_ids: list[str],
    display_limit: int,
) -> tuple[dict[str, object], ...]:
    candidates = read_jsonl(questions_path)
    annotations = {str(item["candidate_id"]): item for item in read_jsonl(annotations_path)}
    selected = _selected_candidates(candidates=candidates, case_ids=case_ids)
    views_by_id: dict[str, dict[str, object]] = {}
    retrievable = tuple(item for item in selected if item["proposed_category"] != "security_negative")
    for candidate in selected:
        if candidate["proposed_category"] == "security_negative":
            views_by_id[str(candidate["candidate_id"])] = {
                "status": "transient_maintainer_review_only",
                "candidate_id": candidate["candidate_id"],
                "question": candidate["question"],
                "proposed_category": candidate["proposed_category"],
                "proposed_expected_domain_ids": candidate["proposed_expected_domain_ids"],
                "proposed_expected_answerability": candidate["proposed_expected_answerability"],
                "candidate_documents": [],
                "review_note": "security_negative_stops_before_retrieval",
                "persistence_allowed": False,
                "maintainer_confirmation": "pending",
            }
    if not retrievable:
        return tuple(views_by_id[str(candidate["candidate_id"])] for candidate in selected)

    token = _required("AGENT_KNOWLEDGE_ADMIN_JWT")
    async with (
        build_knowledge_http_client(_required("AGENT_KNOWLEDGE_ES_BASE_URL")) as es_client,
        build_knowledge_http_client(_required("AGENT_KNOWLEDGE_EMBEDDING_BASE_URL")) as embedding_client,
        build_knowledge_http_client(_required("AGENT_KNOWLEDGE_RERANK_BASE_URL")) as rerank_client,
    ):
        stage = DefaultKnowledgeRetrievalStage(
            search=EsKnowledgeSearchAdapter(HttpxKnowledgeTransport(es_client)),
            embedding=BgeM3EmbeddingAdapter(HttpxKnowledgeTransport(embedding_client)),
            rerank=BgeRerankAdapter(HttpxKnowledgeTransport(rerank_client)),
            final_candidates=10,
        )
        for candidate in retrievable:
            candidate_id = str(candidate["candidate_id"])
            result = await stage.execute(
                plan=_plan(candidate),
                context=_context(candidate_id=candidate_id, token=token),
                timeout_s=25.0,
            )
            if result.kind is not RetrievalStageKind.SUCCESS or result.batch is None:
                raise RuntimeError(f"candidate_review.retrieval_failed:{candidate_id}:{result.kind.value}")
            annotation = annotations.get(candidate_id)
            if annotation is None:
                raise RuntimeError(f"candidate_review.annotation_missing:{candidate_id}")
            _verify_annotation(candidate_id=candidate_id, batch=result.batch, annotation=annotation)
            views_by_id[candidate_id] = _build_transient_view(
                candidate=candidate,
                batch=result.batch,
                display_limit=display_limit,
            )
    return tuple(views_by_id[str(candidate["candidate_id"])] for candidate in selected)


async def _main_async() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", action="append", required=True)
    parser.add_argument("--display-limit", type=int, default=3)
    arguments = parser.parse_args()
    if not 1 <= arguments.display_limit <= _MAX_DISPLAY_CANDIDATES:
        raise RuntimeError("candidate_review.invalid_display_limit")
    root = Path(__file__).resolve().parent
    reviews = await _review(
        questions_path=root / "candidate_questions.v1.jsonl",
        annotations_path=root / "candidate_retrieval_annotations.v1.jsonl",
        case_ids=arguments.case_id,
        display_limit=arguments.display_limit,
    )
    for review in reviews:
        print(json.dumps(review, ensure_ascii=False, separators=(",", ":")))
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
