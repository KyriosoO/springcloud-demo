from __future__ import annotations

import asyncio
import hashlib
import json

import pytest

from agent_runtime.knowledge.contracts import KnowledgeRetrievalContext, RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import KnowledgePathRequest, PathResultFailure, PathResultKind
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpResponse
from tests.helpers import ManualCancellationSignal, scope
from tests.retrieval_helpers import FakeTransport


@pytest.mark.asyncio
async def test_es_adapter_uses_typed_profile_and_original_user_token() -> None:
    content = "税务政策正文"
    response = {
        "schemaVersion": 1, "logicalDomainId": "tax.policy", "retrievalProfileId": "tax-policy-v1",
        "path": "keyword", "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": "a" * 64,
        "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
        "candidates": [{
            "documentId": "d1", "chunkId": "c1", "logicalDomainId": "tax.policy", "title": "标题",
            "content": content, "sourceUrl": None, "documentNumber": None, "writtenDate": None,
            "materialType": "tax_policy", "sourceRank": 1,
            "contentSha256": hashlib.sha256(content.encode()).hexdigest(), "policyRef": "policy-doc-v1",
        }],
    }
    transport = FakeTransport(BoundedHttpResponse(status_code=200, content_type="application/json", content_encoding=None, body=json.dumps(response, ensure_ascii=False).encode()))
    request_scope = scope()
    context = KnowledgeRetrievalContext(
        request_id="r", correlation_id="c", subject="u", user_token=request_scope.context.user_token,
        deadline_monotonic=asyncio.get_running_loop().time() + 5, cancellation=ManualCancellationSignal(),
    )
    result = await EsKnowledgeSearchAdapter(transport).search(
        request=KnowledgePathRequest(
            logical_domain_id="tax.policy", retrieval_profile_id="tax-policy-v1", path=RetrievalPath.KEYWORD,
            query_text="增值税", query_vector=None, candidate_limit=20,
        ),
        context=context, timeout_s=2,
    )

    assert result.kind is PathResultKind.CANDIDATES
    assert ("Authorization", "Bearer header.payload.signature") in transport.requests[0].headers
    body = json.loads(transport.requests[0].body)
    assert set(body) == {"schemaVersion", "logicalDomainId", "retrievalProfileId", "path", "queryText", "queryVector", "limit"}
    assert not any(key in body for key in ("index", "alias", "dsl", "filter"))


@pytest.mark.asyncio
@pytest.mark.parametrize("status,kind", [(401, PathResultKind.FAILURE), (403, PathResultKind.FORBIDDEN), (503, PathResultKind.FAILURE), (504, PathResultKind.TIMEOUT)])
async def test_es_statuses_are_finite_and_error_body_is_not_parsed(status: int, kind: PathResultKind) -> None:
    transport = FakeTransport(BoundedHttpResponse(status_code=status, content_type="text/plain", content_encoding=None, body=b"sensitive sentinel"))
    request_scope = scope()
    context = KnowledgeRetrievalContext(
        request_id="r", correlation_id="c", subject="u", user_token=request_scope.context.user_token,
        deadline_monotonic=asyncio.get_running_loop().time() + 5, cancellation=ManualCancellationSignal(),
    )
    result = await EsKnowledgeSearchAdapter(transport).search(
        request=KnowledgePathRequest(logical_domain_id="tax.policy", retrieval_profile_id="tax-policy-v1", path=RetrievalPath.KEYWORD, query_text="税", query_vector=None, candidate_limit=5),
        context=context, timeout_s=1,
    )
    assert result.kind is kind


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value.update(profileVersion="unexpected"),
        lambda value: value.update(truncated=1),
        lambda value: value.update(indexSnapshotId="not-a-hash"),
        lambda value: value["candidates"][0].update(writtenDate=20250101),
        lambda value: value["candidates"].append(dict(value["candidates"][0], sourceRank=2)),
    ],
)
async def test_es_adapter_rejects_drifted_or_ambiguous_success_contract(mutate: object) -> None:
    content = "税务政策正文"
    response = {
        "schemaVersion": 1, "logicalDomainId": "tax.policy", "retrievalProfileId": "tax-policy-v1",
        "path": "keyword", "profileVersion": "tax-knowledge-search-v1", "indexSnapshotId": "a" * 64,
        "readPolicyVersion": "tax-public-authenticated-v1", "truncated": False,
        "candidates": [{
            "documentId": "d1", "chunkId": "c1", "logicalDomainId": "tax.policy", "title": "标题",
            "content": content, "sourceUrl": None, "documentNumber": None, "writtenDate": None,
            "materialType": "tax_policy", "sourceRank": 1,
            "contentSha256": hashlib.sha256(content.encode()).hexdigest(), "policyRef": "policy-doc-v1",
        }],
    }
    mutate(response)  # type: ignore[operator]
    transport = FakeTransport(BoundedHttpResponse(
        status_code=200,
        content_type="application/json",
        content_encoding=None,
        body=json.dumps(response, ensure_ascii=False).encode(),
    ))
    request_scope = scope()
    context = KnowledgeRetrievalContext(
        request_id="r", correlation_id="c", subject="u", user_token=request_scope.context.user_token,
        deadline_monotonic=asyncio.get_running_loop().time() + 5, cancellation=ManualCancellationSignal(),
    )

    result = await EsKnowledgeSearchAdapter(transport).search(
        request=KnowledgePathRequest(
            logical_domain_id="tax.policy", retrieval_profile_id="tax-policy-v1",
            path=RetrievalPath.KEYWORD, query_text="税", query_vector=None, candidate_limit=5,
        ),
        context=context,
        timeout_s=1,
    )

    assert result.kind is PathResultKind.FAILURE
    assert result.failure is PathResultFailure.INVALID_PROVIDER_RESULT
