from __future__ import annotations

import asyncio

from starlette.requests import Request

from agent_runtime.capability_api.contracts import CancellationSource


class MutableCancellationSignal:
    __slots__ = ("_event", "_source")

    def __init__(self) -> None:
        self._event = asyncio.Event()
        self._source: CancellationSource | None = None

    def cancel(self, source: CancellationSource) -> None:
        if self._source is None:
            self._source = source
            self._event.set()

    def is_cancelled(self) -> bool:
        return self._source is not None

    async def wait_cancelled(self) -> CancellationSource:
        await self._event.wait()
        if self._source is None:
            raise RuntimeError("runtime.cancellation_invariant")
        return self._source


async def watch_disconnect(
    request: Request,
    signal: MutableCancellationSignal,
    poll_interval_s: float,
) -> None:
    while not signal.is_cancelled():
        if await request.is_disconnected():
            signal.cancel(CancellationSource.UPSTREAM_CANCEL)
            return
        await asyncio.sleep(poll_interval_s)
