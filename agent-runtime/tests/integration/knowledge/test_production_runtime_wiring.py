from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable

import httpx
import pytest

from agent_runtime.capability_api.contracts import CapabilityStatus
from agent_runtime.main import build_runtime
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
)
from tests.helpers import scope


_SNAPSHOT_ID = "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed"
_DOCUMENT_IDS = (
    "tax-0001c0a09c307565464b087b",
    "tax-001544ec4d92c5703c34ae07",
    "tax-00229650537a3b3d877107e7",
)


class _FixedStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield self._content


class _KnowledgeModelTransport:
    def __init__(self) -> None:
        self.requests: list[StructuredModelRequest] = []

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        assert call_deadline > asyncio.get_running_loop().time()
        self.requests.append(request)
        payload = json.loads(request.user_payload_json)
        if request.task_id is ModelTaskId.ACTION_SELECTION:
            content = '{"capability_id":"knowledge.query"}'
        elif request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            content = json.dumps(
                {"outcome": "search", "queries": [{"domain_id": "tax.policy", "query": payload["question"]}], "missing_conditions": []},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        elif request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            first = payload["evidence"][0]
            content = json.dumps(
                {
                    "outcome": "answer",
                    "points": [{
                        "evidence_ref": first["evidence_ref"],
                        "quote": first["content"],
                    }],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            raise AssertionError(f"unexpected model task: {request.task_id}")
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=content,
            tool_calls=(),
            usage_total_tokens=0,
        )


class _KnowledgeClientFactory:
    def __init__(self) -> None:
        self.clients: list[httpx.AsyncClient] = []
        self.paths: list[str] = []
        self.es_authorizations: list[str] = []

    def __call__(self, base_url: str) -> httpx.AsyncClient:
        async def handle(request: httpx.Request) -> httpx.Response:
            self.paths.append(request.url.path)
            if request.url.path == "/embed":
                return self._json({"dim": 1024, "vectors": [[0.0] * 1024]})
            if request.url.path == "/rerank":
                value = json.loads(request.content)
                return self._json({
                    "model": "BAAI/bge-reranker-v2-m3",
                    "results": [
                        {"index": index, "text": text, "score": 1.0 - index / 100}
                        for index, text in enumerate(value["documents"])
                    ],
                })
            if request.url.path == "/es/knowledge/search":
                self.es_authorizations.append(request.headers["Authorization"])
                value = json.loads(request.content)
                return self._json(self._search_result(value))
            raise AssertionError(f"unexpected Knowledge path: {request.url.path}")

        client = httpx.AsyncClient(
            base_url=base_url,
            transport=httpx.MockTransport(handle),
            trust_env=False,
        )
        self.clients.append(client)
        return client

    @staticmethod
    def _json(value: object) -> httpx.Response:
        content = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=_FixedStream(content),
        )

    @staticmethod
    def _search_result(request: dict[str, object]) -> dict[str, object]:
        domain_id = request["logicalDomainId"]
        profile_id = request["retrievalProfileId"]
        path = request["path"]
        contents = (
            "现行增值税政策明确规定纳税人应当依法办理申报。",
            "增值税政策适用条件应当以税务机关发布的现行文件为准。",
            "纳税人应当保存能够证明适用税务政策的完整资料。",
        )
        return {
            "schemaVersion": 1,
            "logicalDomainId": domain_id,
            "retrievalProfileId": profile_id,
            "path": path,
            "profileVersion": "tax-knowledge-search-v1",
            "indexSnapshotId": _SNAPSHOT_ID,
            "readPolicyVersion": "tax-public-authenticated-v1",
            "truncated": False,
            "candidates": [
                {
                    "documentId": document_id,
                    "chunkId": f"chunk-{index}",
                    "logicalDomainId": domain_id,
                    "title": f"增值税政策资料{index}",
                    "content": content,
                    "sourceUrl": None,
                    "documentNumber": None,
                    "writtenDate": None,
                    "materialType": "tax_policy",
                    "sourceRank": index,
                    "contentSha256": hashlib.sha256(content.encode()).hexdigest(),
                    "policyRef": "public:tax_policy",
                }
                for index, (document_id, content) in enumerate(
                    zip(_DOCUMENT_IDS, contents, strict=True),
                    1,
                )
            ],
        }


def _enabled_environment() -> dict[str, str]:
    return {
        "AGENT_MODEL_PROVIDER": "stub",
        "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy",
        "AGENT_KNOWLEDGE_ES_BASE_URL": "http://knowledge.test",
    }


@pytest.mark.asyncio
async def test_disabled_entrypoint_never_requires_or_allocates_knowledge_dependencies() -> None:
    factory_calls = 0

    def forbidden_factory(base_url: str) -> httpx.AsyncClient:
        nonlocal factory_calls
        del base_url
        factory_calls += 1
        raise AssertionError("Knowledge client must stay disabled")

    runtime = build_runtime(
        {
            "AGENT_KNOWLEDGE_ENABLED": "false",
            "AGENT_KNOWLEDGE_ES_BASE_URL": "not-an-origin",
            "LLM_API_KEY": "must-not-be-read",
        },
        knowledge_http_client_factory=forbidden_factory,
    )
    question = "现行增值税政策是什么"
    outcome = await runtime.ainvoke(question=question, scope=scope(question))

    assert outcome.status is CapabilityStatus.UNSUPPORTED
    assert factory_calls == 0


def test_enabled_stub_requires_explicit_nonlive_model_transport_before_client_allocation() -> None:
    factory_calls = 0

    def forbidden_factory(base_url: str) -> httpx.AsyncClient:
        nonlocal factory_calls
        del base_url
        factory_calls += 1
        raise AssertionError("Knowledge client must not be allocated")

    with pytest.raises(ValueError, match="knowledge.stub_transport_required"):
        build_runtime(
            _enabled_environment(),
            knowledge_http_client_factory=forbidden_factory,
        )

    assert factory_calls == 0


@pytest.mark.asyncio
async def test_enabled_entrypoint_executes_one_knowledge_action_and_owns_clients() -> None:
    model = _KnowledgeModelTransport()
    clients = _KnowledgeClientFactory()
    runtime = build_runtime(
        _enabled_environment(),
        model_transport=model,
        knowledge_http_client_factory=clients,
    )
    assert isinstance(runtime, ModelContextBindingRuntimeInvoker)
    question = "现行增值税政策有哪些"

    outcome = await runtime.ainvoke(question=question, scope=scope(question))
    await runtime.aclose()
    await runtime.aclose()

    assert outcome.status is CapabilityStatus.SUCCESS, (
        outcome.failure,
        clients.paths,
        clients.es_authorizations,
    )
    assert outcome.capability_id == "knowledge.query"
    assert outcome.user_result is not None
    assert [request.task_id for request in model.requests] == [
        ModelTaskId.ACTION_SELECTION,
        ModelTaskId.KNOWLEDGE_REWRITE,
        ModelTaskId.KNOWLEDGE_SUMMARY,
    ]
    assert clients.paths.count("/embed") == 1
    assert clients.paths.count("/es/knowledge/search") == 2
    assert clients.paths.count("/rerank") == 1
    assert clients.es_authorizations == [
        "Bearer header.payload.signature",
        "Bearer header.payload.signature",
    ]
    assert len(clients.clients) == 3
    assert all(client.is_closed for client in clients.clients)
