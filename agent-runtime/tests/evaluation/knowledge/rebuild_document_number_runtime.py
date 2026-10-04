"""Private owned comparison assembly; no CLI, grant or default execution.

The future outer executor must freeze/validate authorization and fresh snapshots
before calling this seam. This seam owns startup through cleanup, not inventory,
model identity, authorization, scoring or publication. Tests use fake resources.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import importlib.util
import secrets
from types import ModuleType
from typing import TypeVar

import httpcore
import httpx

from agent_runtime.capability_api.contracts import CancellationSignal, OpaqueUserToken
from agent_runtime.knowledge.retrieval.http import (
    BoundedHttpRequest, BoundedHttpResponse, HttpxKnowledgeTransport,
)
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, CleanupReport
from tests.evaluation.knowledge.rebuild_document_number_owned import OwnedJavaResources, ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_projection import ProjectedJavaPair
from tests.evaluation.knowledge.rebuild_document_number_proxy import DocumentNumberProxy
from tests.evaluation.knowledge.rebuild_document_number_stage import StageComparisonResult, StageComparisonSession

_T = TypeVar("_T")
_HEALTH = "/actuator/health/knowledge-validation"
_STARTUP_SECONDS = 30.0


def _client_safe(client: httpx.AsyncClient) -> bool:
    # Same pinned single-send invariant as the synchronous physical proxy;
    # async pool differs, and no custom auth/hook/retry may multiply attempts.
    if (type(client) is not httpx.AsyncClient or httpx.__version__ != "0.28.1"
            or httpcore.__version__ != "1.0.9" or client.is_closed
            or client.follow_redirects or getattr(client, "_trust_env", True)
            or getattr(client, "_auth", object()) is not None or client.cookies or client.params
            or getattr(client, "_mounts", None) != {}
            or client.event_hooks != {"request": [], "response": []}
            or set(client.headers) - {"accept", "accept-encoding", "connection", "user-agent"}):
        return False
    transport = getattr(client, "_transport", None)
    if type(transport) is httpx.MockTransport:
        return True
    pool = getattr(transport, "_pool", None)
    return (type(transport) is httpx.AsyncHTTPTransport and type(pool) is httpcore.AsyncConnectionPool
            and getattr(pool, "_uds", object()) is None and type(getattr(pool, "_retries", None)) is int
            and pool._retries == 0)


class _OwnedTypedTransport:
    def __init__(self, resources: OwnedJavaResources, client: httpx.AsyncClient, port: int) -> None:
        self.resources, self.client, self.port = resources, client, port
        self.delegate = HttpxKnowledgeTransport(client)

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        # Recheck immediately before any in-memory JWT can leave, not merely
        # once during startup. A foreign listener is never stopped or queried.
        self.resources.require_listeners()
        p.require(_client_safe(self.client) and str(self.client.base_url).rstrip("/") ==
                  f"http://127.0.0.1:{self.port}", "runtime_client_drift")
        return await self.delegate.send(request=request, timeout_s=timeout_s)


class _ModelTransport:
    def __init__(self, client: httpx.AsyncClient, port: int) -> None:
        self.client, self.port = client, port
        self.delegate = HttpxKnowledgeTransport(client)

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        p.require(_client_safe(self.client) and str(self.client.base_url).rstrip("/") ==
                  f"http://127.0.0.1:{self.port}", "runtime_client_drift")
        return await self.delegate.send(request=request, timeout_s=timeout_s)


def _warmup_module() -> ModuleType:
    # Reuse the versioned startup payload/strict decoder, not warmup(), which
    # would create an unowned client and hide its send from this ledger.
    spec = importlib.util.spec_from_file_location("document_number_warmup", p.ROOT / "serviceCenter/warmup-knowledge-reranker.py")
    p.require(spec is not None and spec.loader is not None, "runtime_warmup_missing")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _cancel_bound(call: Callable[[], Awaitable[_T]], signal: CancellationSignal) -> _T:
    if signal.is_cancelled():
        raise asyncio.CancelledError
    async def invoke() -> _T:
        return await call()
    work = asyncio.create_task(invoke())
    cancelled = asyncio.create_task(signal.wait_cancelled())
    try:
        await asyncio.wait((work, cancelled), return_when=asyncio.FIRST_COMPLETED)
        if cancelled.done() or signal.is_cancelled():
            raise asyncio.CancelledError
        return work.result()
    finally:
        for task in (work, cancelled):
            if not task.done():
                task.cancel()
        await asyncio.gather(work, cancelled, return_exceptions=True)


async def _exchange(*, client: httpx.AsyncClient, journal: AttemptJournal, kind: str,
                    label: str, method: str, path: str, body: bytes,
                    maximum: int, seconds: float, port: int) -> bytes:
    task = asyncio.current_task()
    if task is not None and task.cancelling():
        raise asyncio.CancelledError
    p.require(_client_safe(client) and str(client.base_url).rstrip("/") ==
              f"http://127.0.0.1:{port}", "runtime_client_drift")
    ticket = journal.ledger.begin(kind, label, body)
    status: int | None = None
    raw: bytes | None = None
    failed = cancelled = False
    loop = asyncio.get_running_loop()
    cutoff = loop.time() + seconds
    try:
        async with asyncio.timeout(seconds) as deadline:
            async with client.stream(method, path, content=body or None,
                    headers={"Accept-Encoding": "identity", "Content-Type": "application/json"},
                    follow_redirects=False, timeout=httpx.Timeout(seconds)) as response:
                status = response.status_code
                lengths = response.headers.get_list("content-length")
                p.require(status == 200
                    and response.headers.get("content-type", "").split(";", 1)[0].strip().lower() == "application/json"
                    and response.headers.get("content-encoding", "identity").lower() == "identity"
                    and (not lengths or len(lengths) == 1 and lengths[0].isascii() and lengths[0].isdecimal()
                         and lengths[0] == str(int(lengths[0])) and int(lengths[0]) <= maximum), "runtime_response_invalid")
                data = bytearray()
                async for part in response.aiter_raw():
                    p.require(len(data) + len(part) <= maximum, "runtime_response_too_large")
                    data.extend(part)
                p.require(0 < len(data) <= maximum and (not lengths or int(lengths[0]) == len(data)),
                          "runtime_response_invalid")
                raw = bytes(data)
        # A provider may swallow the work-task cancellation and return UP.
        # Never allow that late success to start the next health/prewarm send.
        if task is not None and task.cancelling():
            raise asyncio.CancelledError
        p.require(not deadline.expired() and loop.time() < cutoff, "runtime_response_late")
    except asyncio.CancelledError:
        cancelled = True
    except Exception:
        failed = True
    # Protocol/size failure can still have an HTTP status. Preserve that
    # finite receipt, then abort separately; never persist provider exceptions.
    journal.ledger.finish(ticket, "cancelled" if cancelled else "completed" if status is not None
                          else "transport_failed", None if cancelled else status)
    if failed or cancelled:
        journal.ledger.abort()
        if cancelled:
            raise asyncio.CancelledError from None
        raise p.ProtocolError("runtime_startup_request_failed") from None
    assert raw is not None
    return raw


@dataclass(frozen=True, slots=True)
class OwnedComparisonCapture:
    stage: StageComparisonResult
    cleanup: CleanupReport
    counted_attempts: tuple[tuple[str, int], ...]
    quality_assessment: str = "Not assessed"
    release_allowed: bool = False


class OwnedComparisonRuntime:
    """Once-only assembly using the same projected JAR lease and attempt log.

    Expected metadata hashes are caller inputs, not validated current snapshots.
    No invocation path in this module authorizes real execution.
    """
    def __init__(self, *, pair: ProjectedJavaPair, journal: AttemptJournal, binding: ReadBinding,
                 ports: tuple[int, int, int, int], metadata_sha256: tuple[tuple[str, str], ...],
                 postcheck: Callable[[], Awaitable[None]] | None = None) -> None:
        p.require(postcheck is None or callable(postcheck), "runtime_postcheck_invalid")
        self.pair, self.journal, self.binding = pair, journal, binding
        self.ports, self.metadata_sha256 = ports, metadata_sha256
        self.postcheck = postcheck
        self.attempted = False

    def _identity_ready(self, *, post: bool) -> None:
        ledger = self.journal.identity_ledger
        if ledger is not None:
            state = ledger.view()
            p.require(ledger.phases == ("pre", "post") and not state["stopped"] and state["pending"] == 0
                and state["counts"] == {"pre": 4, "post": 4 if post else 0}, "runtime_identity_incomplete")

    async def _startup(self, resources: OwnedJavaResources) -> None:
        # Native process/port observation is not an HTTP readiness retry. Both
        # owned listeners must exist before the first counted health request.
        from tests.evaluation.knowledge import rebuild_b_local_runner as shared
        async with asyncio.timeout(_STARTUP_SECONDS):
            for arm, port in zip(p.ARMS, self.ports[:2], strict=True):
                process = resources.processes[arm]
                while True:
                    p.require(process.poll() is None and not self.journal.ledger.view()["stopped"], "runtime_startup_stopped")
                    try:
                        owner = shared._listener_owner(port)
                    except shared.BLocalRunError as error:
                        p.require(error.reason == "listener_owner_mismatch", "runtime_listener_unavailable")
                    else:
                        p.require(owner == process.pid, "runtime_listener_changed")
                        break
                    await asyncio.sleep(0.05)
        resources.require_listeners()

    async def _execute(self, resources: OwnedJavaResources, signal: CancellationSignal) -> StageComparisonResult:
        from tests.evaluation.knowledge import rebuild_b_local_runner as shared
        backend = resources.open_backend()
        proxies = tuple(DocumentNumberProxy(draft=self.pair.draft, arm=arm, port=self.ports[i + 2],
            binding=self.binding, metadata_sha256=self.metadata_sha256,
            ledger=self.journal.ledger, backend=backend) for i, arm in enumerate(p.ARMS))
        for proxy in proxies:
            resources.add_proxy(proxy)
            proxy.start()
        secret = secrets.token_bytes(48)
        for arm in p.ARMS:
            resources.start_java(arm, binding=self.binding, secret=secret)
        await self._startup(resources)
        typed = tuple(resources.open_client(port) for port in self.ports[:2])
        for arm, client, port in zip(p.ARMS, typed, self.ports[:2], strict=True):
            resources.require_listeners()
            raw = await _exchange(client=client, journal=self.journal, kind="javaHealth", label=f"startup/{arm}/health",
                method="GET", path=_HEALTH, body=b"", maximum=4096, seconds=2, port=port)
            p.require(p._decode(raw) == {"status": "UP"}, "runtime_java_not_ready")
        p.require(all(all(count == 2 for count in proxy.metadata_counts.values()) for proxy in proxies),
                  "runtime_profile_incomplete")
        embedding, rerank = resources.open_client(8908), resources.open_client(8909)
        warmup = _warmup_module()
        raw = await _exchange(client=rerank, journal=self.journal, kind="prewarmRerank", label="startup/rerank",
            method="POST", path="/rerank", body=p.canonical({"query": "合成文本的本地推理预热检查",
                "documents": warmup.DOCUMENTS, "top_n": 40, "normalize": True}),
            maximum=warmup.MAX_BYTES, seconds=warmup.DEADLINE_S, port=8909)
        warmup.validate(raw)
        resources.require_listeners()
        stage = StageComparisonSession(pair=self.pair, ledger=self.journal.ledger,
            typed=(_OwnedTypedTransport(resources, typed[0], self.ports[0]),
                   _OwnedTypedTransport(resources, typed[1], self.ports[1])),
            embedding=_ModelTransport(embedding, 8908), rerank=_ModelTransport(rerank, 8909),
            physical=(proxies[0], proxies[1]), binding=self.binding)
        result = await stage.evaluate(token=OpaqueUserToken.from_raw(shared._jwt(secret)), cancellation=signal)
        # The same ledger is stopped/sealed by owned cleanup. A successful
        # postflight must run here, never after evaluate() returns or in a new
        # uncounted log. Cancellation still drains this work before cleanup.
        if self.postcheck is not None:
            if signal.is_cancelled():
                raise asyncio.CancelledError
            await self.postcheck()
        self._identity_ready(post=True)
        return result

    async def evaluate(self, *, cancellation: CancellationSignal) -> OwnedComparisonCapture:
        p.require(not self.attempted and not self.journal.ledger.view()["stopped"], "runtime_already_attempted")
        self.attempted = True
        resources: OwnedJavaResources | None = None
        result: StageComparisonResult | None = None
        cleanup: CleanupReport | None = None
        failed = cancelled = False
        try:
            if cancellation.is_cancelled():
                raise asyncio.CancelledError
            self._identity_ready(post=False)
            self.pair.verify_artifacts()
            resources = OwnedJavaResources(pair=self.pair, journal=self.journal, ports=self.ports)
            result = await _cancel_bound(lambda: self._execute(resources, cancellation), cancellation)
        except asyncio.CancelledError:
            cancelled = True
        except Exception:
            failed = True
        finally:
            if resources is not None:
                # Shield the owned cleanup from client cancellation. Drain the
                # task even if cancellation arrives repeatedly during close.
                task = asyncio.create_task(resources.close())
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        cancelled = True
                    except Exception:
                        break
                try:
                    cleanup = task.result()
                except (Exception, asyncio.CancelledError):
                    failed = True
            else:
                self.journal.ledger.abort()
                if self.journal.identity_ledger is not None:
                    self.journal.identity_ledger.abort()
        if failed:
            raise p.ProtocolError("runtime_comparison_failed") from None
        if cancelled:
            raise asyncio.CancelledError from None
        assert result is not None and cleanup is not None
        return OwnedComparisonCapture(result, cleanup, tuple(self.journal.ledger.counts.items()))
