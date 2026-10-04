"""Private pinned one-send guard, independent of parsers and source records."""
from __future__ import annotations

import httpcore
import httpx


def _single_send_client(client: httpx.Client) -> bool:
    """Pinned httpx 0.28.1/httpcore 1.0.9 seam; layout drift fails closed.

    Auth flows, redirects, mounts, hooks or custom transports can multiply or
    redirect one stream call. Only an unmodified no-retry native transport, or
    the exact in-memory MockTransport used by tests, may reach this scanner.
    """
    if (type(client) is not httpx.Client or httpx.__version__ != "0.28.1"
            or httpcore.__version__ != "1.0.9"):
        return False
    if (getattr(client, "_auth", object()) is not None or len(client.cookies) != 0 or len(client.params) != 0
            or getattr(client, "_mounts", None) != {}
            or client.event_hooks != {"request": [], "response": []}
            or set(client.headers) - {"accept", "accept-encoding", "connection", "user-agent"}):
        return False
    transport = getattr(client, "_transport", None)
    if type(transport) is httpx.MockTransport:
        return True
    if type(transport) is not httpx.HTTPTransport:
        return False
    pool = getattr(transport, "_pool", None)
    retries = getattr(pool, "_retries", None)
    return (type(pool) is httpcore.ConnectionPool and getattr(pool, "_uds", object()) is None
            and type(retries) is int and retries == 0)
