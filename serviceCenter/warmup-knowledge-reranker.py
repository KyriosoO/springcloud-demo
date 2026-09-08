"""One synthetic startup check; never a user-query retry or an online timeout override."""
from __future__ import annotations

import asyncio
import json
import math
import sys
import time

import httpx

ORIGIN = "http://127.0.0.1:8909"
DEADLINE_S = 30.0
MAX_BYTES = 2 * 1024 * 1024
DOCUMENTS = tuple(
    (f"合成容量验证片段{i:02d}。该文本仅用于本地推理预热，不是法律依据，不含真实语料。" * 110)[:4096]
    for i in range(40)
)


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def _constant(value: str) -> object:
    raise ValueError("nonfinite_json")


def validate(raw: bytes) -> None:
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_constant)
    if type(value) is not dict or set(value) != {"model", "results"} or value["model"] != "BAAI/bge-reranker-v2-m3":
        raise ValueError("invalid_model_response")
    rows = value["results"]
    if type(rows) is not list or len(rows) != len(DOCUMENTS):
        raise ValueError("invalid_results")
    seen: set[int] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"index", "text", "score"}:
            raise ValueError("invalid_row")
        index, score = row["index"], row["score"]
        if (type(index) is not int or index in seen or not 0 <= index < len(DOCUMENTS)
                or row["text"] != DOCUMENTS[index] or type(score) not in (int, float)
                or not math.isfinite(score)):
            raise ValueError("invalid_row")
        seen.add(index)


async def warmup(*, transport: httpx.AsyncBaseTransport | None = None) -> dict[str, object]:
    started = time.monotonic()
    payload = {"query": "合成文本的本地推理预热检查", "documents": DOCUMENTS, "top_n": 40, "normalize": True}
    async with httpx.AsyncClient(base_url=ORIGIN, transport=transport, trust_env=False,
                                follow_redirects=False, timeout=None) as client:
        async with asyncio.timeout(DEADLINE_S):
            async with client.stream("POST", "/rerank", json=payload,
                    headers={"Accept-Encoding": "identity"}) as response:
                length = response.headers.get("Content-Length")
                if (response.status_code != 200
                        or response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json"
                        or response.headers.get("Content-Encoding", "identity").strip().lower() != "identity"
                        or length is not None and (not length.isascii() or not length.isdecimal()
                            or len(length) > 10 or length != str(int(length)) or int(length) > MAX_BYTES)):
                    raise ValueError("invalid_response_headers")
                raw = bytearray()
                async for part in response.aiter_raw():
                    if len(raw) + len(part) > MAX_BYTES:
                        raise ValueError("response_too_large")
                    raw.extend(part)
                validate(bytes(raw))
                if time.monotonic() - started >= DEADLINE_S:
                    raise TimeoutError("warmup_timeout")
    return {"status": "ready", "rerankCalls": 1, "items": len(DOCUMENTS),
            "elapsedMs": int((time.monotonic() - started) * 1000), "clientClosed": client.is_closed}


def main() -> int:
    if len(sys.argv) != 1:
        print('{"status":"invalid_arguments","rerankCalls":0}')
        return 2
    try:
        result = asyncio.run(warmup())
    except (ValueError, UnicodeError, OverflowError, httpx.HTTPError, TimeoutError) as error:
        # Never print exception text, response, environment or the synthetic payload.
        kind = "timeout" if isinstance(error, TimeoutError) else "dependency_invalid"
        print(json.dumps({"status": "failed", "reason": kind, "retry": 0}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
