from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date

from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import (
    AuthorizedKnowledgeCandidate,
    KnowledgePathRequest,
    PathResultFailure,
    PathResultKind,
    PathRetrievalResult,
)
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, LocalFakeHttpTransport, RetrievalTransportError

PROFILE_BY_DOMAIN = {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}
_SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}")


def _reject_constant(_: str) -> None:
    raise ValueError("knowledge.invalid_provider_result")


def _text(value: object, *, maximum: int, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if type(value) is not str:
        raise ValueError("knowledge.invalid_provider_result")
    normalized = unicodedata.normalize("NFC", value)
    if not 1 <= len(normalized) <= maximum or any(unicodedata.category(character) == "Cc" for character in normalized):
        raise ValueError("knowledge.invalid_provider_result")
    return normalized


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("knowledge.duplicate_json_key")
        result[key] = value
    return result


class EsKnowledgeSearchAdapter:
    __slots__ = ("_expected_profile_version", "_transport")

    def __init__(self, transport: LocalFakeHttpTransport, *, expected_profile_version: str = "tax-knowledge-search-v1") -> None:
        if expected_profile_version != "tax-knowledge-search-v1":
            raise ValueError("knowledge.invalid_profile_version")
        self._transport = transport
        self._expected_profile_version = expected_profile_version

    async def search(
        self,
        *,
        request: KnowledgePathRequest,
        context: KnowledgeRetrievalContext,
        timeout_s: float,
    ) -> PathRetrievalResult:
        payload = {
            "schemaVersion": 1,
            "logicalDomainId": request.logical_domain_id,
            "retrievalProfileId": request.retrieval_profile_id,
            "path": request.path.value,
            "queryText": request.query_text,
            "queryVector": request.query_vector,
            "limit": request.candidate_limit,
        }
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        try:
            response = await self._transport.send(
                request=BoundedHttpRequest(
                    method="POST", relative_path="/es/knowledge/search",
                    headers=(
                        ("Accept-Encoding", "identity"),
                        ("Authorization", f"Bearer {context.user_token.reveal_for_outbound()}"),
                        ("Content-Type", "application/json"),
                    ),
                    body=body, max_response_bytes=2 * 1024 * 1024,
                ),
                timeout_s=min(timeout_s, 5.0),
            )
        except TimeoutError:
            return self._terminal(request, PathResultKind.TIMEOUT)
        except Exception:
            return self._terminal(request, PathResultKind.FAILURE, PathResultFailure.RETRIEVAL_FAILURE)
        status = response.status_code
        if status == 403:
            return self._terminal(request, PathResultKind.FORBIDDEN)
        if status == 401:
            return self._terminal(request, PathResultKind.FAILURE, PathResultFailure.READ_DECISION_UNVERIFIABLE)
        if status == 503:
            return self._terminal(request, PathResultKind.FAILURE, PathResultFailure.READ_AUTHORITY_FAILURE)
        if status == 504:
            return self._terminal(request, PathResultKind.TIMEOUT)
        if status in (400, 415, 204):
            return self._terminal(request, PathResultKind.FAILURE, PathResultFailure.INVALID_PROVIDER_RESULT)
        if status != 200:
            return self._terminal(request, PathResultKind.FAILURE, PathResultFailure.RETRIEVAL_FAILURE)
        try:
            return self._decode(request, response.content_type, response.content_encoding, response.body)
        except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
            return self._terminal(request, PathResultKind.FAILURE, PathResultFailure.INVALID_PROVIDER_RESULT)

    @staticmethod
    def _terminal(request: KnowledgePathRequest, kind: PathResultKind, failure: PathResultFailure | None = None) -> PathRetrievalResult:
        return PathRetrievalResult(
            kind=kind,
            logical_domain_id=request.logical_domain_id,
            retrieval_profile_id=request.retrieval_profile_id,
            path=request.path,
            failure=failure,
        )

    def _decode(self, request: KnowledgePathRequest, content_type: str | None, content_encoding: str | None, body: bytes) -> PathRetrievalResult:
        if content_type != "application/json" or content_encoding not in (None, "identity") or not body or len(body) > 2 * 1024 * 1024:
            raise ValueError("knowledge.invalid_provider_result")
        raw = json.loads(
            body.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=_reject_constant,
        )
        required = {
            "schemaVersion", "logicalDomainId", "retrievalProfileId", "path", "profileVersion",
            "indexSnapshotId", "readPolicyVersion", "truncated", "candidates",
        }
        if type(raw) is not dict or set(raw) != required or raw["schemaVersion"] != 1:
            raise ValueError("knowledge.invalid_provider_result")
        if (raw["logicalDomainId"], raw["retrievalProfileId"], raw["path"]) != (
            request.logical_domain_id, request.retrieval_profile_id, request.path.value,
        ):
            raise ValueError("knowledge.invalid_provider_result")
        if (
            raw["profileVersion"] != self._expected_profile_version
            or type(raw["readPolicyVersion"]) is not str
            or _SAFE_ID.fullmatch(raw["readPolicyVersion"]) is None
            or type(raw["indexSnapshotId"]) is not str
            or _LOWER_HEX_64.fullmatch(raw["indexSnapshotId"]) is None
            or type(raw["truncated"]) is not bool
        ):
            raise ValueError("knowledge.invalid_provider_result")
        if type(raw["candidates"]) is not list or len(raw["candidates"]) > request.candidate_limit:
            raise ValueError("knowledge.invalid_provider_result")
        candidates: list[AuthorizedKnowledgeCandidate] = []
        identities: set[tuple[str, str]] = set()
        fields = {
            "documentId", "chunkId", "logicalDomainId", "title", "content", "sourceUrl",
            "documentNumber", "writtenDate", "materialType", "sourceRank", "contentSha256", "policyRef",
        }
        for item in raw["candidates"]:
            if type(item) is not dict or set(item) != fields or item["logicalDomainId"] != request.logical_domain_id:
                raise ValueError("knowledge.invalid_provider_result")
            document_id = _text(item["documentId"], maximum=256)
            chunk_id = _text(item["chunkId"], maximum=256)
            assert document_id is not None and chunk_id is not None
            identity = (document_id, chunk_id)
            if identity in identities:
                raise ValueError("knowledge.invalid_provider_result")
            identities.add(identity)
            written_raw = item["writtenDate"]
            if written_raw is None:
                written = None
            elif type(written_raw) is str:
                written = date.fromisoformat(written_raw)
            else:
                raise ValueError("knowledge.invalid_provider_result")
            title = _text(item["title"], maximum=256)
            content = _text(item["content"], maximum=4096)
            source_url = _text(item["sourceUrl"], maximum=1024, optional=True)
            document_number = _text(item["documentNumber"], maximum=256, optional=True)
            material_type = _text(item["materialType"], maximum=256)
            if type(item["sourceRank"]) is not int or not 1 <= item["sourceRank"] <= request.candidate_limit:
                raise ValueError("knowledge.invalid_provider_result")
            if type(item["contentSha256"]) is not str or _LOWER_HEX_64.fullmatch(item["contentSha256"]) is None:
                raise ValueError("knowledge.invalid_provider_result")
            if type(item["policyRef"]) is not str or _SAFE_ID.fullmatch(item["policyRef"]) is None:
                raise ValueError("knowledge.invalid_provider_result")
            assert title is not None and content is not None and material_type is not None
            candidate = AuthorizedKnowledgeCandidate(
                document_id=document_id, chunk_id=chunk_id, domain_id=item["logicalDomainId"],
                title=title, content=content, source_url=source_url,
                document_number=document_number, written_date=written, material_type=material_type,
                source_rank=item["sourceRank"], content_sha256=item["contentSha256"],
                read_policy_version=raw["readPolicyVersion"], policy_ref=item["policyRef"],
                index_snapshot_id=raw["indexSnapshotId"],
            )
            if hashlib.sha256(candidate.content.encode("utf-8")).hexdigest() != candidate.content_sha256:
                raise ValueError("knowledge.invalid_provider_result")
            candidates.append(candidate)
        if tuple(item.source_rank for item in candidates) != tuple(range(1, len(candidates) + 1)):
            raise ValueError("knowledge.invalid_provider_result")
        return PathRetrievalResult(
            kind=PathResultKind.CANDIDATES if candidates else PathResultKind.NO_RESULT,
            logical_domain_id=request.logical_domain_id,
            retrieval_profile_id=request.retrieval_profile_id,
            path=request.path,
            profile_version=raw["profileVersion"], index_snapshot_id=raw["indexSnapshotId"],
            read_policy_version=raw["readPolicyVersion"], truncated=raw["truncated"],
            candidates=tuple(candidates),
        )
