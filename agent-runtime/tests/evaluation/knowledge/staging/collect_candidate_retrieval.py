from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import unicodedata
from pathlib import Path

from agent_runtime.capability_api.contracts import OpaqueUserToken
from agent_runtime.knowledge.contracts import (
    KnowledgeRetrievalContext,
    KnowledgeRetrievalPlan,
    RetrievalPath,
    RetrievalPlanItem,
    RetrievalStageKind,
)
from agent_runtime.knowledge.retrieval.bge_embedding import BgeM3EmbeddingAdapter
from agent_runtime.knowledge.retrieval.bge_rerank import BgeRerankAdapter
from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import HttpxKnowledgeTransport, build_knowledge_http_client
from agent_runtime.knowledge.retrieval.stage import DefaultKnowledgeRetrievalStage
from tests.evaluation.knowledge.staging.validate_candidate_package import read_jsonl
from tests.helpers import ManualCancellationSignal


_PROFILE_BY_DOMAIN = {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}


def _required(name: str) -> str:
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(f"candidate_retrieval.missing_environment:{name}")
    return value


def _evidence_id(candidate: AuthorizedKnowledgeCandidate) -> str:
    identity = (
        unicodedata.normalize("NFC", candidate.document_id)
        + "\n"
        + unicodedata.normalize("NFC", candidate.chunk_id)
        + "\n"
        + candidate.content_sha256
    ).encode("utf-8")
    return "ev-" + hashlib.sha256(identity).hexdigest()


def _retrieval_domains(candidate: dict[str, object]) -> tuple[str, ...]:
    raw_domains = candidate["proposed_expected_domain_ids"]
    if not isinstance(raw_domains, list):
        raise RuntimeError("candidate_retrieval.invalid_domains")
    domains_list: list[str] = []
    for value in raw_domains:
        if not isinstance(value, str):
            raise RuntimeError("candidate_retrieval.invalid_domains")
        domains_list.append(value)
    domains = tuple(domains_list)
    if domains:
        return domains
    return ("tax.policy", "tax.law")


def _plan(candidate: dict[str, object]) -> KnowledgeRetrievalPlan:
    question = str(candidate["question"])
    items: list[RetrievalPlanItem] = []
    for domain in _retrieval_domains(candidate):
        for path in (RetrievalPath.KEYWORD, RetrievalPath.VECTOR):
            items.append(
                RetrievalPlanItem(
                    logical_domain_id=domain,
                    path=path,
                    query_text=question,
                    candidate_limit=10,
                    ordinal=len(items) + 1,
                )
            )
    return KnowledgeRetrievalPlan(
        items=tuple(items),
        selected_domain_ids=_retrieval_domains(candidate),
        config_version="knowledge-flow-config-v1",
    )


def _context(*, candidate_id: str, token: str) -> KnowledgeRetrievalContext:
    loop = asyncio.get_running_loop()
    return KnowledgeRetrievalContext(
        request_id=f"kp5-staging-{candidate_id}",
        correlation_id=f"kp5-staging-{candidate_id}",
        subject="kp5-staging-user",
        user_token=OpaqueUserToken.from_raw(token),
        deadline_monotonic=loop.time() + 30.0,
        cancellation=ManualCancellationSignal(),
    )


async def _collect(*, questions_path: Path) -> tuple[dict[str, object], ...]:
    candidates = read_jsonl(questions_path)
    expected_snapshots = {
        "tax.policy": _required("AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID"),
        "tax.law": _required("AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID"),
    }
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
        annotations: list[dict[str, object]] = []
        for candidate in candidates:
            candidate_id = str(candidate["candidate_id"])
            if candidate["proposed_category"] == "security_negative":
                annotations.append(
                    {
                        "candidate_id": candidate_id,
                        "retrieval_status": "skipped_by_design",
                        "retrieval_reason": "security_negative_pre_retrieval_stop",
                        "retrieval_profile_version": None,
                        "index_snapshot_ids": [],
                        "candidate_documents": [],
                        "document_relevance_review": "pending_maintainer_review",
                        "evidence_relevance_review": "pending_maintainer_review",
                        "selected_document_ids": [],
                        "selected_evidence_ids": [],
                        "reviewer": None,
                        "reviewed_at": None,
                    }
                )
                continue
            result = await stage.execute(
                plan=_plan(candidate),
                context=_context(candidate_id=candidate_id, token=token),
                timeout_s=25.0,
            )
            if result.kind not in {RetrievalStageKind.SUCCESS, RetrievalStageKind.NO_RESULT}:
                raise RuntimeError(f"candidate_retrieval.failed:{candidate_id}:{result.kind.value}")
            expected = {expected_snapshots[domain] for domain in _retrieval_domains(candidate)}
            if result.kind is RetrievalStageKind.SUCCESS:
                if result.batch is None or set(result.batch.index_snapshot_ids) != expected:
                    raise RuntimeError(f"candidate_retrieval.snapshot_mismatch:{candidate_id}")
                documents = [
                    {
                        "rank": item.rank,
                        "document_id": item.candidate.document_id,
                        "evidence_id": _evidence_id(item.candidate),
                        "domain_ids": list(item.domain_ids),
                    }
                    for item in result.batch.candidates
                ]
                status = "retrieved"
                snapshots = list(result.batch.index_snapshot_ids)
                profile_version = result.batch.profile_version
            else:
                documents = []
                status = "no_result"
                snapshots = [expected_snapshots[domain] for domain in _retrieval_domains(candidate)]
                profile_version = "tax-knowledge-search-v1"
            annotations.append(
                {
                    "candidate_id": candidate_id,
                    "retrieval_status": status,
                    "retrieval_reason": "none",
                    "retrieval_profile_version": profile_version,
                    "index_snapshot_ids": snapshots,
                    "candidate_documents": documents,
                    "document_relevance_review": "pending_maintainer_review",
                    "evidence_relevance_review": "pending_maintainer_review",
                    "selected_document_ids": [],
                    "selected_evidence_ids": [],
                    "reviewer": None,
                    "reviewed_at": None,
                }
            )
    return tuple(annotations)


async def _main_async() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    staging_root = Path(__file__).resolve().parent
    output = arguments.output.resolve()
    expected_output = (staging_root / "candidate_retrieval_annotations.v1.jsonl").resolve()
    if output != expected_output or output.exists():
        raise RuntimeError("candidate_retrieval.output_not_new_staging_asset")
    annotations = await _collect(questions_path=arguments.questions.resolve())
    encoded = b"".join(
        json.dumps(item, ensure_ascii=False, sort_keys=False, separators=(",", ":")).encode("utf-8") + b"\n"
        for item in annotations
    )
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, output)
    print(json.dumps({"status": "candidate_only", "annotation_count": len(annotations)}, separators=(",", ":")))
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
