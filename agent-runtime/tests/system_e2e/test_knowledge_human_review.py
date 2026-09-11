from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import socket
import time

import httpx
import pytest

from agent_runtime.knowledge.evidence.contracts import KnowledgeSummaryInput, SummaryCoverageInput, SummaryEvidenceInput
from tests.system_e2e import knowledge_human_review as review


def sample():
    case = dict(caseId="SYNTHETIC-1", question="合成问题")
    summary = KnowledgeSummaryInput(schema_version=1, question=case["question"],
        coverage=SummaryCoverageInput(retrieval_complete=True, domain_coverage_complete=True),
        evidence=(SummaryEvidenceInput(evidence_ref="e1", content="合成授权正文 <script>alert(1)</script>"),))
    response = dict(status="success", result=dict(answerSummary="合成回答", points=[dict(quote="合成授权正文", citation=dict(
        title="合成来源", evidenceId="synthetic-id", sourceUrl="https://should-not-display.example"))]),
        rawModel="RAW-MODEL-MUST-NOT-LEAK", jwt="JWT-MUST-NOT-LEAK")
    return case, response, summary


def ready_session(**kwargs):
    session = review.ReviewSession(**kwargs)
    session.mark_ready(dict(ready=True))
    return session


def decision(state, *, useful=True):
    return dict(caseId=state["packet"]["caseId"], nonce=state["nonce"], acknowledged=True,
                **{k: True for k in review.FIELDS}, reason="none") | dict(useful=useful, reason="none" if useful else "coverage")


def pending(session):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        state = session.state()
        if state["status"] == "review":
            return state
        time.sleep(.005)
    raise AssertionError("synthetic review did not become pending")


def test_projection_uses_actual_policy_input_and_public_result_only():
    case, response, summary = sample()
    value = review.packet(case, response, summary)
    assert value["answerSummary"] == response["result"]["answerSummary"]
    assert value["evidence"][0]["content"] == summary.evidence[0].content
    assert "RAW-MODEL" not in json.dumps(value) and "JWT-MUST" not in json.dumps(value)
    assert "sourceUrl" not in json.dumps(value)
    with pytest.raises(ValueError, match="question_mismatch"):
        review.packet(case, response, replace(summary, question="another request"))
    with pytest.raises(ValueError, match="packet_invalid"):
        review.packet(case, response, replace(summary, evidence=(replace(summary.evidence[0], content="X" * 131073),)))


@pytest.mark.parametrize("change", [
    {"extra": True}, {"faithful": 1}, {"faithful": "true"}, {"acknowledged": False},
    {"nonce": "old"}, {"caseId": "another"}, {"reason": "unknown"}, {"reason": "coverage"},
    {"useful": False}, {"reason": []},
])
def test_exact_verdict_rejects_invalid_and_cross_request(change):
    valid = decision(dict(packet=dict(caseId="C1"), nonce="current"))
    with pytest.raises(ValueError):
        review.verdict(valid | change, "C1", "current")


@pytest.mark.parametrize("raw", [b'{"ready":true,"ready":true}', b'{"x":NaN}', b'{"x":Infinity}', b'invalid'])
def test_strict_json(raw):
    with pytest.raises(ValueError):
        review.exact_json(raw)


@pytest.mark.parametrize("useful", [True, False])
def test_first_human_decision_is_final_and_record_has_no_text(useful, capsys, caplog):
    session = ready_session()
    value = review.packet(*sample())
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(session.review, value)
        state = pending(session)
        selected = decision(state, useful=useful)
        session.submit(selected)
        with pytest.raises(ValueError):
            session.submit(selected)
        record = future.result(timeout=2)
    assert record["status"] == "assessed" and record["useful"] is useful
    assert record["packetSha256"] == review.sha(value)
    assert session.pending is session.decision is None
    assert session.state() == {"status": "waiting"}
    with pytest.raises(ValueError):
        session.review(value)
    visible = review.canonical(record).decode() + capsys.readouterr().out + caplog.text
    assert all(text not in visible for text in ("合成", "alert(1)", session.token, state["nonce"]))


def test_timeout_close_and_total_wait_do_not_pass():
    session = ready_session(case_timeout=.02, total_timeout=.03)
    value = review.packet(*sample())
    first = session.review(value)
    assert first["status"] == "not_assessed" and first["reason"] == "timeout"
    assert session.pending is None and session.remaining < .02
    second = session.review(value | {"caseId": "SYNTHETIC-2"})
    assert second["status"] == "not_assessed" and session.remaining == 0
    with ThreadPoolExecutor(max_workers=1) as pool:
        session = ready_session()
        future = pool.submit(session.review, value)
        pending(session)
        session.close()
        assert future.result(timeout=1)["reason"] == "closed"
    assert session.token == "" and session.pending is None
    assert session.state() == {"status": "closed"}
    with pytest.raises(ValueError):
        session.mark_ready(dict(ready=True))


def test_unready_session_cannot_accept_a_case():
    session = review.ReviewSession(case_timeout=.01)
    assert not session.wait_ready()
    with pytest.raises(ValueError):
        session.review(review.packet(*sample()))
    assert session.pending is None


def test_real_local_http_auth_origin_host_exact_body_and_cleanup(capsys):
    session = review.ReviewSession()
    with review.ReviewPortal(session) as portal, httpx.Client(base_url=portal.origin, trust_env=False) as client:
        port = portal.server.server_port
        assert client.get("/").status_code == 200
        assert session.token not in client.get("/app.js").text
        assert client.get("/state").status_code == 403
        headers = {"X-Review-Token": session.token}
        assert client.get("/state", headers=headers).json() == {"status": "ready_required"}
        assert client.get("/state", headers=headers | {"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/state", headers=headers | {"Host": "evil.example"}).status_code == 403
        assert client.post("/ready", headers=headers, json={"ready": True}).status_code == 403
        headers["Origin"] = portal.origin
        for body in (b'{"ready":true,"ready":true}', b'{"ready":1}', b'{"ready":true,"extra":1}', b'[]'):
            assert client.post("/ready", headers=headers | {"Content-Type": "application/json"}, content=body).status_code == 400
        assert not session.ready
        assert client.post("/ready", headers=headers, json={"ready": True}).status_code == 200
        assert session.wait_ready()
        assert client.post("/ready", headers=headers, json={"ready": True}).status_code == 400
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(session.review, review.packet(*sample()))
            pending(session)
            response = client.get("/state", headers=headers)
            assert response.headers["Cache-Control"] == "no-store"
            assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
            assert "合成" in response.text
            selected = decision(response.json())
            assert client.post("/decision", headers=headers, json=selected | {"extra": "raw"}).status_code == 400
            assert not future.done()
            assert client.post("/decision", headers=headers, json=selected).status_code == 200
            assert future.result(timeout=1)["status"] == "assessed"
            assert "合成" not in client.get("/state", headers=headers).text
            assert client.post("/decision", headers=headers, json=selected).status_code == 400
        assert client.post("/close", headers=headers, json={"close": True}).status_code == 200
        assert client.get("/state", headers=headers).status_code == 403
    assert not portal.thread.is_alive() and session.closed
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", port)) != 0
    assert capsys.readouterr().out == ""


def test_ui_has_no_default_verdict_or_content_execution_or_durable_storage():
    root = Path(review.__file__)
    html, script = root.with_suffix(".html").read_text(encoding="utf-8"), root.with_suffix(".js").read_text(encoding="utf-8")
    assert ".textContent =" in script and "replaceChildren()" in script
    assert "innerHTML" not in script and "localStorage" not in script and "sessionStorage" not in script
    assert " checked" not in html and " selected" not in html and "input.checked =" not in script
    assert "history.replaceState(null" in script
    assert "https://" not in html + script


def test_browser_bootstrap_does_not_print_token(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(review.webbrowser, "open", lambda url, **kwargs: seen.append(url) or True)
    with review.ReviewPortal(review.ReviewSession()) as portal:
        token = portal.session.token
        assert portal.open_browser()
        assert seen == [portal.origin + "/#" + token]
    assert token not in capsys.readouterr().out
