from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import httpx
import uvicorn

from agent_runtime.api.app import create_app
from agent_runtime.api.settings import RuntimeHttpSettings
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.graph.state import AgentSemanticOutcome
from agent_runtime.main import build_runtime
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelProviderFailureKind,
    ModelTaskId,
    ModelTransportError,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
)
from tests.system_e2e.knowledge_nonlive_evidence import (
    EXPECTED_CASE_IDS,
    write_knowledge_nonlive_evidence,
)


_SNAPSHOT_ID = "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed"
_DOCUMENT_IDS = (
    "tax-0001c0a09c307565464b087b",
    "tax-001544ec4d92c5703c34ae07",
    "tax-00229650537a3b3d877107e7",
)
_CALL_KEYS = ("action", "rewrite", "summary", "businessModel", "embed", "search", "rerank")


class _FixedStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes) -> None:
        self._content = content

    async def __aiter__(self):  # type: ignore[no-untyped-def]
        yield self._content


class _Probe:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()

    def snapshot(self) -> dict[str, int]:
        return {key: self.counts[key] for key in _CALL_KEYS}

    def delta(self, before: dict[str, int]) -> dict[str, int]:
        return {key: self.counts[key] - before[key] for key in _CALL_KEYS}


class _KnowledgeModelTransport:
    def __init__(self, probe: _Probe) -> None:
        self._probe = probe

    async def complete(
        self,
        request: StructuredModelRequest,
        *,
        call_deadline: float,
    ) -> StructuredModelResponse:
        if call_deadline <= asyncio.get_running_loop().time():
            raise TimeoutError("knowledge_nonlive.deadline")
        payload = json.loads(request.user_payload_json)
        if request.task_id is ModelTaskId.ACTION_SELECTION:
            self._probe.counts["action"] += 1
            question = payload["question"]
            content = (
                '{"capability_id":"knowledge.query","second":"employee.search"}'
                if "第二动作" in question
                else '{"capability_id":"knowledge.query"}'
            )
        elif request.task_id is ModelTaskId.KNOWLEDGE_REWRITE:
            self._probe.counts["rewrite"] += 1
            question = payload["question"]
            if "改写失败" in question:
                raise ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)
            content = json.dumps(
                {"candidates": [question]},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        elif request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY:
            self._probe.counts["summary"] += 1
            question = payload["question"]
            if "摘要失败" in question:
                raise ModelTransportError(ModelProviderFailureKind.PROVIDER_FAILURE)
            evidence = payload["evidence"]
            first = evidence[0]
            if "非法引用" in question:
                points = [{"evidence_ref": "e999", "quote": first["content"]}]
            elif "重复引用" in question:
                points = [
                    {"evidence_ref": first["evidence_ref"], "quote": first["content"]},
                    {"evidence_ref": first["evidence_ref"], "quote": first["content"]},
                ]
            else:
                points = [{"evidence_ref": first["evidence_ref"], "quote": first["content"]}]
            content = json.dumps(
                {"outcome": "answer", "points": points},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        else:
            self._probe.counts["businessModel"] += 1
            raise AssertionError("knowledge_nonlive.business_model_forbidden")
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.STOP,
            content=content,
            tool_calls=(),
            usage_total_tokens=0,
        )


class _KnowledgeClientFactory:
    def __init__(self, probe: _Probe, *, allowed_tokens: frozenset[str]) -> None:
        self._probe = probe
        self._allowed_authorizations = frozenset(f"Bearer {token}" for token in allowed_tokens)
        self._current_query = ""
        self.clients: list[httpx.AsyncClient] = []

    def __call__(self, base_url: str) -> httpx.AsyncClient:
        client = httpx.AsyncClient(
            base_url=base_url,
            transport=httpx.MockTransport(self._handle),
            trust_env=False,
        )
        self.clients.append(client)
        return client

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/embed":
            self._probe.counts["embed"] += 1
            payload = json.loads(request.content)
            self._current_query = payload["texts"][0]
            return self._json({"dim": 1024, "vectors": [[0.0] * 1024]})
        if request.url.path == "/rerank":
            self._probe.counts["rerank"] += 1
            payload = json.loads(request.content)
            return self._json({
                "model": "BAAI/bge-reranker-v2-m3",
                "results": [
                    {"index": index, "text": text, "score": 1.0 - index / 100}
                    for index, text in enumerate(payload["documents"])
                ],
            })
        if request.url.path != "/es/knowledge/search":
            raise AssertionError("knowledge_nonlive.physical_path_forbidden")
        self._probe.counts["search"] += 1
        payload = json.loads(request.content)
        query = payload["queryText"] or self._current_query
        if request.headers.get("Authorization") not in self._allowed_authorizations:
            return self._response(403, b"")
        if "全部检索失败" in query:
            return self._response(500, b"")
        if "单路失败" in query and payload["path"] == "vector":
            return self._response(500, b"")
        if "不存在资料" in query:
            return self._json(self._search_result(payload, candidates=()))
        unknown_policy = "未分类策略" in query
        return self._json(self._search_result(payload, candidates=self._candidates(
            payload["logicalDomainId"],
            unknown_policy=unknown_policy,
        )))

    @staticmethod
    def _response(status: int, content: bytes) -> httpx.Response:
        return httpx.Response(status, stream=_FixedStream(content))

    @staticmethod
    def _json(value: object) -> httpx.Response:
        content = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            stream=_FixedStream(content),
        )

    @staticmethod
    def _candidates(domain_id: str, *, unknown_policy: bool) -> tuple[dict[str, object], ...]:
        contents = (
            "现行税务政策和法律规定纳税人应当依法办理申报。",
            "税务政策适用条件应当以税务机关发布的现行文件为准。",
            "纳税人应当保存能够证明适用税务政策的完整资料。",
        )
        return tuple({
            "documentId": "tax-unknown-policy" if unknown_policy else document_id,
            "chunkId": f"chunk-{index}",
            "logicalDomainId": domain_id,
            "title": f"税务资料{index}",
            "content": content,
            "sourceUrl": None,
            "documentNumber": None,
            "writtenDate": None,
            "materialType": "tax_policy",
            "sourceRank": index,
            "contentSha256": hashlib.sha256(content.encode()).hexdigest(),
            "policyRef": "public:tax_policy",
        } for index, (document_id, content) in enumerate(
            zip(_DOCUMENT_IDS, contents, strict=True),
            1,
        ))

    @staticmethod
    def _search_result(
        request: dict[str, object],
        *,
        candidates: tuple[dict[str, object], ...],
    ) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "logicalDomainId": request["logicalDomainId"],
            "retrievalProfileId": request["retrievalProfileId"],
            "path": request["path"],
            "profileVersion": "tax-knowledge-search-v1",
            "indexSnapshotId": _SNAPSHOT_ID,
            "readPolicyVersion": "tax-public-authenticated-v1",
            "truncated": False,
            "candidates": list(candidates),
        }


class KnowledgeNonLiveRuntime:
    def __init__(
        self,
        *,
        delegate: ModelContextBindingRuntimeInvoker,
        evidence_path: Path,
        probe: _Probe,
        clients: _KnowledgeClientFactory,
    ) -> None:
        self._delegate = delegate
        self._evidence_path = evidence_path
        self._probe = probe
        self._clients = clients
        self._cases: list[dict[str, object]] = []
        self._case_ids: set[str] = set()
        self._closed = False
        self._lock = asyncio.Lock()

    async def ainvoke(self, *, question: str, scope: RequestExecutionScope) -> AgentSemanticOutcome:
        case_id = scope.context.correlation_id
        before = self._probe.snapshot()
        outcome = await self._delegate.ainvoke(question=question, scope=scope)
        if case_id in EXPECTED_CASE_IDS:
            if case_id in self._case_ids:
                raise RuntimeError("knowledge_nonlive.duplicate_case")
            self._case_ids.add(case_id)
            self._cases.append({
                "caseId": case_id,
                "status": outcome.status.value,
                "capabilityId": outcome.capability_id,
                "failureCode": outcome.failure.code if outcome.failure is not None else None,
                "calls": self._probe.delta(before),
            })
        return outcome

    async def aclose(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            failure: BaseException | None = None
            try:
                await self._delegate.aclose()
            except BaseException as exc:
                failure = exc
            totals = self._probe.snapshot()
            write_knowledge_nonlive_evidence(
                self._evidence_path,
                cases=tuple(self._cases),
                totals=totals,
                runtime_closed=failure is None,
                clients_closed=len(self._clients.clients) == 3
                and all(client.is_closed for client in self._clients.clients),
            )
            if failure is not None:
                raise failure


def _required(env: Mapping[str, str], key: str) -> str:
    value = env.get(key)
    if value is None or not value.strip():
        raise ValueError(f"knowledge_nonlive.env_missing:{key}")
    return value


def build_knowledge_nonlive_runtime(
    env: Mapping[str, str] | None = None,
) -> KnowledgeNonLiveRuntime:
    active = dict(os.environ if env is None else env)
    if active.get("AGENT_MODEL_PROVIDER", "stub") != "stub":
        raise ValueError("knowledge_nonlive.model_provider_must_be_stub")
    evidence_path = Path(_required(active, "KNOWLEDGE_NONLIVE_EVIDENCE_PATH")).resolve()
    probe = _Probe()
    client_factory = _KnowledgeClientFactory(
        probe,
        allowed_tokens=frozenset({
            _required(active, "KNOWLEDGE_NONLIVE_ADMIN_TOKEN"),
            _required(active, "KNOWLEDGE_NONLIVE_VIEWER_TOKEN"),
        }),
    )
    active.update({
        "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
        "AGENT_KNOWLEDGE_ES_BASE_URL": "http://knowledge.invalid",
        "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL": "http://127.0.0.1:18908",
        "AGENT_KNOWLEDGE_RERANK_BASE_URL": "http://127.0.0.1:18909",
    })
    active.pop("LLM_API_KEY", None)
    runtime = build_runtime(
        active,
        model_transport=_KnowledgeModelTransport(probe),
        knowledge_http_client_factory=client_factory,
    )
    if not isinstance(runtime, ModelContextBindingRuntimeInvoker):
        raise TypeError("knowledge_nonlive.runtime_invalid")
    return KnowledgeNonLiveRuntime(
        delegate=runtime,
        evidence_path=evidence_path,
        probe=probe,
        clients=client_factory,
    )


async def _serve(settings: RuntimeHttpSettings, stop_path: Path) -> None:
    stop_path.parent.mkdir(parents=True, exist_ok=True)
    stop_path.unlink(missing_ok=True)
    app = create_app(settings, build_knowledge_nonlive_runtime)
    server = uvicorn.Server(uvicorn.Config(
        app=app,
        host=settings.host,
        port=settings.port,
        workers=1,
        http="h11",
        h11_max_incomplete_event_size=settings.max_incomplete_event_bytes,
        access_log=False,
        log_level="warning",
    ))

    async def watch_stop() -> None:
        while not stop_path.exists():
            await asyncio.sleep(0.05)
        server.should_exit = True

    watcher = asyncio.create_task(watch_stop())
    try:
        await server.serve()
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass


def main() -> None:
    settings = RuntimeHttpSettings.from_env()
    stop_path = Path(_required(os.environ, "KNOWLEDGE_NONLIVE_STOP_PATH")).resolve()
    asyncio.run(_serve(settings, stop_path))


if __name__ == "__main__":
    main()
