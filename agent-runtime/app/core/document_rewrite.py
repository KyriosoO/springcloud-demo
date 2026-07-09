"""文档查询改写端点的运行时逻辑。"""

from __future__ import annotations

import json
import math
import uuid
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.llm_client import LlmClient, get_llm_client


DOCUMENT_REWRITE_SYSTEM_PROMPT = """You rewrite a document search query into safer retrieval candidates.

Return one JSON object only. Do not use Markdown.
Return schema:
{"candidates":[{"text":"...", "intentLabel":"...", "confidence":0.0}]}

Rules:
- Return only rewrite candidates. Do not return Elasticsearch DSL, filters, ACL, index alias, profile, topK, sort, or execution plan.
- Keep candidates in the same language as requestData.language when possible.
- Do not invent domain, material type, permission scope, metadata filters, dates, document numbers, or authorities.
- Keep each candidate concise and semantically close to requestData.query.
"""

FORBIDDEN_REWRITE_FIELDS = {
    "dsl",
    "queryDsl",
    "filter",
    "filters",
    "aclScope",
    "indexAlias",
    "retrievalProfile",
    "profileVersion",
    "topK",
    "sort",
    "sorts",
    "queryVector",
    "embedding",
}


class DocumentRewriteCandidate(BaseModel):
    """Runtime 返回的单条不可信改写候选。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str = Field(..., min_length=1, max_length=256)
    intent_label: str | None = Field(None, alias="intentLabel", max_length=64)
    confidence: float | None = Field(None, ge=0.0, le=1.0)


class DocumentRewriteRequest(BaseModel):
    """Java 文档改写请求；不包含 ACL、index alias、profile 或 ES DSL。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    request_id: str = Field(..., alias="requestId", min_length=1, max_length=128)
    query: str = Field(..., min_length=1, max_length=500)
    domain: str = Field(..., min_length=1, max_length=128)
    material_type: str | None = Field(None, alias="materialType", max_length=128)
    language: str = Field("zh-CN", max_length=32)
    max_candidates: int = Field(3, alias="maxCandidates", ge=1, le=10)
    timeout_ms: int | None = Field(None, alias="timeoutMs", ge=1, le=60_000)


class DocumentRewriteResponse(BaseModel):
    """文档改写响应；所有候选仍需 Java 再校验。"""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    candidates: list[DocumentRewriteCandidate] = Field(default_factory=list, max_length=10)
    diagnostic_id: str = Field(..., alias="diagnosticId", min_length=1)
    model: str | None = None


class RuntimeDocumentRewritePlanner:
    """调用 LLM 生成文档改写候选，不生成任何执行计划。"""

    def __init__(self, llm_client: LlmClient):
        self._llm_client = llm_client

    async def rewrite(self, request: DocumentRewriteRequest) -> DocumentRewriteResponse:
        request_payload = request.model_dump(by_alias=True, mode="json", exclude_none=False)
        raw = await self._llm_client.generate_plan_json(
            DOCUMENT_REWRITE_SYSTEM_PROMPT,
            {"requestData": request_payload},
        )
        payload = _json_object(raw)
        if _contains_forbidden_field(payload):
            candidates: list[DocumentRewriteCandidate] = []
        else:
            candidates = _normalize_candidates(payload.get("candidates"), request)
        return DocumentRewriteResponse(
            candidates=candidates,
            diagnosticId="runtime-rewrite-" + uuid.uuid4().hex,
            model=getattr(self._llm_client, "model_name", None),
        )


def _json_object(raw: str) -> dict[str, Any]:
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("document rewrite output must be a JSON object")
    return parsed


def _contains_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(forbidden.lower() == str(key).lower() for forbidden in FORBIDDEN_REWRITE_FIELDS):
                return True
            if _contains_forbidden_field(child):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_field(child) for child in value)
    return False


def _normalize_candidates(
    raw_candidates: Any,
    request: DocumentRewriteRequest,
) -> list[DocumentRewriteCandidate]:
    if not isinstance(raw_candidates, list):
        return []
    candidates: list[DocumentRewriteCandidate] = []
    seen: set[str] = set()
    for item in raw_candidates:
        text = _candidate_text(item)
        if text is None:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        candidate = DocumentRewriteCandidate(
            text=text,
            intentLabel=_candidate_label(item),
            confidence=_candidate_confidence(item),
        )
        candidates.append(candidate)
        if len(candidates) >= request.max_candidates:
            break
    return candidates


def _candidate_text(item: Any) -> str | None:
    if isinstance(item, str):
        text = item
    elif isinstance(item, dict):
        text = item.get("text")
    else:
        return None
    if not isinstance(text, str):
        return None
    normalized = " ".join(text.split())
    return normalized[:256] if normalized else None


def _candidate_label(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    value = item.get("intentLabel") or item.get("intent_label")
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized[:64] if normalized else None


def _candidate_confidence(item: Any) -> float | None:
    if not isinstance(item, dict):
        return None
    value = item.get("confidence")
    if not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return max(0.0, min(1.0, float(value)))


@lru_cache
def get_document_rewrite_planner() -> RuntimeDocumentRewritePlanner:
    """缓存的文档改写 planner 工厂函数。"""
    return RuntimeDocumentRewritePlanner(get_llm_client())
