"""DR-KRET-033: synthetic startup only, never real service calls in pytest."""
import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("reranker_warmup", REPO / "serviceCenter/warmup-knowledge-reranker.py")
warmup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(warmup)


def valid_response():
    return {"model": "BAAI/bge-reranker-v2-m3", "results": [
        {"index": i, "text": text, "score": 0.5} for i, text in enumerate(warmup.DOCUMENTS)]}


@pytest.mark.parametrize("fault", ["model", "root_extra", "not_object", "rows_empty", "row_extra",
    "index_bool", "index_negative", "index_duplicate", "index_float", "text", "score_bool", "score_inf", "score_string"])
def test_strict_contract(fault):
    data = valid_response()
    if fault == "model": data["model"] = "wrong"
    elif fault == "root_extra": data["extra"] = None
    elif fault == "not_object": data = []
    elif fault == "rows_empty": data["results"] = []
    elif fault == "row_extra": data["results"][0]["extra"] = 1
    elif fault.startswith("index_"):
        data["results"][0]["index"] = {"index_bool": False, "index_negative": -1, "index_duplicate": 1, "index_float": 0.0}[fault]
    elif fault == "text": data["results"][0]["text"] = "incorrect"
    elif fault.startswith("score_"):
        data["results"][0]["score"] = {"score_bool": True, "score_inf": float("inf"), "score_string": "0.5"}[fault]
    with pytest.raises(ValueError):
        warmup.validate(json.dumps(data).encode())


@pytest.mark.parametrize("raw", [b'{"model":1,"model":2}', b'{"x":NaN}', b'\xff'])
def test_duplicate_nonfinite_and_unicode(raw):
    with pytest.raises((ValueError, UnicodeError)):
        warmup.validate(raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "status", "mime", "encoding", "declared_size", "actual_size", "timeout", "transport"])
async def test_single_fixed_request_and_cleanup(monkeypatch, fault):
    calls, closed = [], []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            if fault == "timeout": await asyncio.sleep(1)
            yield b"x" * (warmup.MAX_BYTES + 1) if fault == "actual_size" else json.dumps(valid_response()).encode()
        async def aclose(self): closed.append(True)
    async def handle(request):
        calls.append(request)
        assert str(request.url) == "http://127.0.0.1:8909/rerank" and request.method == "POST"
        assert "authorization" not in request.headers and request.headers["Accept-Encoding"] == "identity"
        payload = json.loads(request.content)
        assert set(payload) == {"query", "documents", "top_n", "normalize"}
        assert payload["top_n"] == 40 and payload["normalize"] is True
        assert payload["documents"] == list(warmup.DOCUMENTS)
        assert len(payload["documents"]) == 40 and all(len(d) == 4096 for d in payload["documents"])
        if fault == "transport": raise httpx.ConnectError("synthetic error")
        headers = {"Content-Type": "text/html" if fault == "mime" else "application/json"}
        if fault == "encoding": headers["Content-Encoding"] = "gzip"
        if fault == "declared_size": headers["Content-Length"] = str(warmup.MAX_BYTES + 1)
        return httpx.Response(302 if fault == "status" else 200, headers=headers, stream=Body())
    if fault == "timeout": monkeypatch.setattr(warmup, "DEADLINE_S", 0.01)
    if fault:
        with pytest.raises((ValueError, TimeoutError, httpx.ConnectError)):
            await warmup.warmup(transport=httpx.MockTransport(handle))
    else:
        result = await warmup.warmup(transport=httpx.MockTransport(handle))
        assert result["status"] == "ready" and result["clientClosed"] and result["rerankCalls"] == 1
    assert len(calls) == 1
    if fault != "transport": assert closed == [True]


def test_startup_hook_after_build_before_launch_and_not_planonly_or_disabled():
    text = (REPO / "serviceCenter/run-all-services.ps1").read_text(encoding="utf-8")
    marker = "Invoke-Checked $RuntimePython @((Join-Path $PSScriptRoot 'warmup-knowledge-reranker.py')) $RepoRoot"
    position = text.index(marker)
    assert text.count(marker) == 1
    assert text.index("if ($PlanOnly)") < text.index("Install-Projects\n}") < position
    assert text.rfind("if ($EnableKnowledge)", 0, position) > text.index("if (-not $SkipInfrastructureCheck)")
    assert position < text.index("New-Item -ItemType Directory -Force -Path $LogRoot")
    assert position < text.index("foreach ($service in $Services) {", text.index("$started = [System.Collections.ArrayList]::new()"))


def test_cli_does_not_accept_endpoint_or_input_override(monkeypatch, capsys):
    monkeypatch.setattr(warmup.sys, "argv", ["warmup.py", "--endpoint=https://external.invalid"])
    assert warmup.main() == 2
    assert json.loads(capsys.readouterr().out)["rerankCalls"] == 0


def test_cli_error_is_finite_not_raw_exception(monkeypatch, capsys):
    monkeypatch.setattr(warmup.sys, "argv", ["warmup.py"])
    async def fail(): raise ValueError("unsafe raw response must not appear")
    monkeypatch.setattr(warmup, "warmup", fail)
    assert warmup.main() == 1
    output = capsys.readouterr().out
    assert "unsafe" not in output and json.loads(output)["reason"] == "dependency_invalid"
