"""Ephemeral, loopback-only human appraisal. Never records displayed content."""
from __future__ import annotations

import hashlib
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import threading
import time
from typing import Any, cast
import webbrowser

FIELDS = ("faithful", "relevant", "sufficientForInitialAnswer", "useful")
REASONS = {"none", "quote_context", "relevance", "coverage", "gold_issue"}
MAX_PACKET_BYTES = 131072
MAX_POST_BYTES = 2048


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def exact_json(raw: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    def nonfinite(_: str) -> None:
        raise ValueError("nonfinite")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def packet(case: dict[str, Any], response: dict[str, Any], summary_input: Any) -> dict[str, Any]:
    """Project only the actual public answer and same-request policy-visible input."""
    result = response.get("result")
    if response.get("status") != "success" or not isinstance(result, dict) or summary_input is None:
        raise ValueError("review.answer_unavailable")
    if summary_input.question != case["question"]:
        raise ValueError("review.question_mismatch")
    points = result.get("points")
    if not isinstance(points, list) or not 1 <= len(points) <= 8 or not 1 <= len(summary_input.evidence) <= 8:
        raise ValueError("review.shape_invalid")
    projected = []
    for point in points:
        citation = point.get("citation") if isinstance(point, dict) else None
        if not isinstance(citation, dict) or not isinstance(point.get("quote"), str):
            raise ValueError("review.point_invalid")
        projected.append(dict(quote=point["quote"], citation={k: citation[k] for k in
            ("evidenceId", "domainIds", "title", "documentNumber", "writtenDate") if k in citation}))
    value = dict(caseId=case["caseId"], question=case["question"], answerSummary=result.get("answerSummary"),
        points=projected, evidence=[dict(evidenceRef=e.evidence_ref, content=e.content,
            domainIds=e.domain_ids, title=e.title, documentNumber=e.document_number, writtenDate=e.written_date)
            for e in summary_input.evidence])
    if not isinstance(value["answerSummary"], str) or len(canonical(value)) > MAX_PACKET_BYTES:
        raise ValueError("review.packet_invalid")
    return value


def verdict(value: Any, case_id: str, nonce: str) -> dict[str, Any]:
    required = {"caseId", "nonce", "acknowledged", "reason", *FIELDS}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("review.verdict_shape")
    if value["caseId"] != case_id or value["nonce"] != nonce or value["acknowledged"] is not True:
        raise ValueError("review.verdict_binding")
    if (any(type(value[k]) is not bool for k in FIELDS)
            or not isinstance(value["reason"], str) or value["reason"] not in REASONS):
        raise ValueError("review.verdict_type")
    if all(value[k] for k in FIELDS) != (value["reason"] == "none"):
        raise ValueError("review.reason_mismatch")
    return {k: value[k] for k in (*FIELDS, "reason")}


class ReviewSession:
    def __init__(self, *, case_timeout: float = 600, total_timeout: float = 1800):
        if not 0 < case_timeout <= 600 or not 0 < total_timeout <= 1800:
            raise ValueError("review.timeout_invalid")
        self.case_timeout = case_timeout
        self.remaining = total_timeout
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Condition()
        self.ready = False
        self.closed = False
        self.pending: dict[str, Any] | None = None
        self.decision: dict[str, Any] | None = None
        self.seen: set[str] = set()

    def state(self) -> dict[str, Any]:
        with self.lock:
            if self.closed:
                return dict(status="closed")
            if self.pending is not None:
                return dict(status="review", **self.pending)
            return dict(status="waiting" if self.ready else "ready_required")

    def mark_ready(self, value: Any) -> None:
        with self.lock:
            if value != {"ready": True} or type(value.get("ready")) is not bool:
                raise ValueError("review.ready_invalid")
            if self.closed or self.ready:
                raise ValueError("review.ready_repeated")
            self.ready = True
            self.lock.notify_all()

    def wait_ready(self) -> bool:
        with self.lock:
            self.lock.wait_for(lambda: self.ready or self.closed, timeout=self.case_timeout)
            return self.ready and not self.closed

    def submit(self, value: Any) -> None:
        with self.lock:
            if self.closed or self.pending is None or self.decision is not None:
                raise ValueError("review.not_pending")
            self.decision = verdict(value, self.pending["packet"]["caseId"], self.pending["nonce"])
            # The response is no longer retrievable once its single verdict is accepted.
            self.pending = None
            self.lock.notify_all()

    def review(self, value: dict[str, Any]) -> dict[str, Any]:
        raw = canonical(value)
        if len(raw) > MAX_PACKET_BYTES:
            raise ValueError("review.packet_oversize")
        case_id = value["caseId"]
        with self.lock:
            if not self.ready or self.closed or self.pending is not None or case_id in self.seen:
                raise ValueError("review.lifecycle_invalid")
            self.seen.add(case_id)
            self.decision = None
            self.pending = dict(nonce=secrets.token_urlsafe(24), packet=exact_json(raw))
            start = time.monotonic()
            try:
                self.lock.wait_for(lambda: self.decision is not None or self.closed,
                                   timeout=min(self.case_timeout, self.remaining))
                # A HTTP worker may have changed this while Condition released its lock.
                accepted = cast(dict[str, Any] | None, self.decision)
                result = dict(method="user_interactive", packetSha256=hashlib.sha256(raw).hexdigest(),
                              questionSha256=sha(value["question"]))
                if accepted is None:
                    return dict(**result, status="not_assessed", reason="closed" if self.closed else "timeout")
                return dict(**result, status="assessed", **accepted)
            finally:
                self.remaining = max(0, self.remaining - (time.monotonic() - start))
                self.pending = self.decision = None

    def close(self) -> None:
        with self.lock:
            self.closed = True
            self.pending = self.decision = None
            self.token = ""
            self.lock.notify_all()


class ReviewPortal:
    """Owns one temporary HTTP listener; static UI contains no credentials/data."""
    def __init__(self, session: ReviewSession):
        self.session = session
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.server.daemon_threads = True
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(3)

            def log_message(self, format: str, *args: Any) -> None:
                pass

            def send_body(self, code: int, body: bytes = b"", content_type: str = "application/json") -> None:
                self.send_response(code)
                self.send_header("Content-Type", content_type + "; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
                self.end_headers()
                self.wfile.write(body)

            def allowed(self, *, private: bool) -> bool:
                if self.headers.get_all("Host") != [owner.origin.removeprefix("http://")]:
                    return False
                origins = self.headers.get_all("Origin")
                if origins is not None and origins != [owner.origin]:
                    return False
                if self.command == "POST" and origins != [owner.origin]:
                    return False
                if not private:
                    return True
                values = self.headers.get_all("X-Review-Token") or []
                token = owner.session.token
                return bool(token and len(values) == 1 and values[0].isascii() and hmac.compare_digest(values[0], token))

            def do_GET(self) -> None:
                if not self.allowed(private=self.path not in ("/", "/app.js", "/style.css")):
                    self.send_body(403)
                    return
                if self.path == "/state":
                    self.send_body(200, canonical(owner.session.state()))
                elif self.path in ("/", "/app.js", "/style.css"):
                    ext = {"/": "html", "/app.js": "js", "/style.css": "css"}[self.path]
                    content_type = {"html": "text/html", "js": "text/javascript", "css": "text/css"}[ext]
                    self.send_body(200, Path(__file__).with_suffix("." + ext).read_bytes(), content_type)
                else:
                    self.send_body(404)

            def do_POST(self) -> None:
                if not self.allowed(private=True):
                    self.send_body(403)
                    return
                if self.path not in ("/ready", "/decision", "/close"):
                    self.send_body(404)
                    return
                try:
                    lengths = self.headers.get_all("Content-Length") or []
                    if (len(lengths) != 1 or not lengths[0].isdigit()
                            or not 0 < int(lengths[0]) <= MAX_POST_BYTES
                            or self.headers.get_all("Content-Type") != ["application/json"]
                            or self.headers.get("Transfer-Encoding") is not None):
                        raise ValueError("review.body_invalid")
                    value = exact_json(self.rfile.read(int(lengths[0])))
                    if not isinstance(value, dict):
                        raise ValueError("review.body_shape")
                    if self.path == "/ready":
                        owner.session.mark_ready(value)
                    elif self.path == "/decision":
                        owner.session.submit(value)
                    else:
                        if value != {"close": True} or value["close"] is not True:
                            raise ValueError("review.close_invalid")
                        owner.session.close()
                    self.send_body(200, b'{"accepted":true}')
                except (ValueError, TypeError, KeyError, UnicodeError):
                    self.send_body(400)

        return Handler

    def __enter__(self) -> ReviewPortal:
        self.thread.start()
        return self

    def open_browser(self) -> bool:
        # No console URL or durable token file; fragment never reaches the HTTP server.
        return webbrowser.open(self.origin + "/#" + self.session.token, new=1)

    def __exit__(self, *args: Any) -> None:
        self.session.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
