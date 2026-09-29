"""Opt-in current-root to isolated real typed-read check; never calls an external model.

Run only with KNOWLEDGE_REAL_TYPED_OPT_IN=1 and the SHA-256 of the current
serviceCenter/knowledge-runtime-binding.v2.json in KNOWLEDGE_REAL_TYPED_BINDING_SHA256.
The test owns the Java process on 19201; ES and local BGE remain read-only inputs.
"""
from __future__ import annotations

import asyncio
import base64
from collections import Counter
from contextlib import contextmanager
from dataclasses import replace
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
from typing import Iterator

import httpx
import pytest

from agent_runtime.adapters.http_transport import HttpxBusinessDomainTransport
from agent_runtime.capability_api.contracts import CapabilityStatus, OpaqueUserToken
from agent_runtime.core.execution import RequestExecutionScope
from agent_runtime.knowledge.evidence.summary_task_v9 import OUTPUT_NAME as SUMMARY_OUTPUT_NAME
from agent_runtime.knowledge.intent_task_v12 import OUTPUT_NAME as INTENT_OUTPUT_NAME
from agent_runtime.main import build_runtime
from agent_runtime.model.context import ModelContextBindingRuntimeInvoker
from agent_runtime.model.contracts import (
    ModelTaskId,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredToolCall,
)
from tests.helpers import scope


_REPO = Path(__file__).resolve().parents[3]
_PORTS = {"search": 19201, "embed": 8908, "rerank": 8909}
_PATHS = {"search": "/es/knowledge/search", "embed": "/embed", "rerank": "/rerank"}
_LIMITS = {"search": 2, "embed": 1, "rerank": 1}
_QUESTION = "增值税政策有哪些"


class _SecretBytes:
    def __init__(self, raw: bytes) -> None:
        self.raw = raw

    def __repr__(self) -> str:
        return "<redacted test secret>"


class _SecretText:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def __repr__(self) -> str:
        return "<redacted test token>"


class _SecretEnvironment(dict[str, str]):
    def __repr__(self) -> str:
        return "<redacted test environment>"


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _user_token(secret: bytes) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT", "kid": "ACTIVE"}
    claims = {"sub": "synthetic-knowledge-read-user", "token_type": "user",
              "role": ["ADMIN"], "iat": now, "exp": now + 300}
    unsigned = ".".join(_b64url(json.dumps(value, separators=(",", ":")).encode())
                        for value in (header, claims))
    signature = hmac.new(secret, unsigned.encode("ascii"), hashlib.sha256).digest()
    return f"{unsigned}.{_b64url(signature)}"


def _binding() -> dict[str, str]:
    path = _REPO / "serviceCenter/knowledge-runtime-binding.v2.json"
    raw = path.read_bytes()
    expected = os.environ.get("KNOWLEDGE_REAL_TYPED_BINDING_SHA256", "")
    if len(expected) != 64 or hashlib.sha256(raw).hexdigest() != expected:
        raise AssertionError("knowledge_real_typed.binding_not_confirmed")
    value = json.loads(raw)
    if not isinstance(value, dict) or value.get("schemaVersion") != 1:
        raise AssertionError("knowledge_real_typed.binding_invalid")
    return value


def _preflight(binding: dict[str, str]) -> None:
    for port in (19201,):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    for port in (9200, 8908, 8909):
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    profile = _REPO / "es-query-service/src/main/resources/application-knowledge-live.yml"
    compiled = _REPO / "es-query-service/target/classes/application-knowledge-live.yml"
    if profile.read_bytes() != compiled.read_bytes():
        raise AssertionError("knowledge_real_typed.compiled_profile_stale")
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                      follow_redirects=False, timeout=3) as client:
        alias = client.get(f"/_alias/{binding['readAlias']}")
        alias.raise_for_status()
        if list(alias.json()) != [binding["expectedIndexName"]]:
            raise AssertionError("knowledge_real_typed.alias_drift")
        index = binding["expectedIndexName"]
        settings = client.get(f"/{index}/_settings", params={"filter_path": "*.settings.index.uuid"})
        settings.raise_for_status()
        if settings.json()[index]["settings"]["index"]["uuid"] != binding["expectedIndexUuid"]:
            raise AssertionError("knowledge_real_typed.index_uuid_drift")
        mapping = client.get(f"/{index}/_mapping", params={"filter_path": "*.mappings._meta"})
        mapping.raise_for_status()
        if mapping.json()[index]["mappings"]["_meta"]["mapping_version"] != binding["mappingVersion"]:
            raise AssertionError("knowledge_real_typed.mapping_drift")


def _startup_failure_kind(log_path: Path) -> str:
    # Only fixed categories may leave this test; raw startup logs can contain credentials.
    output = log_path.read_bytes().lower()
    for marker, category in (
        (b"failed to bind properties", "binding"),
        (b"failed to configure a datasource", "datasource"),
        (b"communications link failure", "database_connect"),
        (b"access denied for user", "database_auth"),
        (b"could not resolve placeholder", "missing_property"),
        (b"unsatisfieddependencyexception", "dependency"),
        (b"beancreationexception", "bean_creation"),
        (b"port 19201 was already in use", "port_conflict"),
        (b"unable to start web server", "web_server"),
    ):
        if marker in output:
            return category
    return "other"


@contextmanager
def _isolated_es_service(binding: dict[str, str]) -> Iterator[_SecretText]:
    jar = _REPO / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
    java_home = os.environ.get("JAVA_HOME")
    java = Path(java_home, "bin", "java.exe") if java_home else None
    if java is None or not java.is_file() or not jar.is_file():
        raise AssertionError("knowledge_real_typed.java_artifact_missing")
    java_version = subprocess.run([java, "-version"], capture_output=True, check=False, timeout=5)
    if java_version.returncode != 0 or b'version "25.' not in java_version.stderr:
        raise AssertionError("knowledge_real_typed.java_25_required")
    secret = _SecretBytes(secrets.token_bytes(48))
    token = _SecretText(_user_token(secret.raw))
    child_env = _SecretEnvironment({key: os.environ[key] for key in (
        "SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP", "USERPROFILE",
        "APPDATA", "LOCALAPPDATA",
    ) if key in os.environ})
    child_env["COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"] = base64.b64encode(secret.raw).decode("ascii")
    for env_name, field in (
        ("READ_ALIAS", "readAlias"), ("EXPECTED_INDEX_NAME", "expectedIndexName"),
        ("EXPECTED_INDEX_UUID", "expectedIndexUuid"), ("MAPPING_VERSION", "mappingVersion"),
        ("POLICY_SNAPSHOT_ID", "policySnapshotId"), ("LAW_SNAPSHOT_ID", "lawSnapshotId"),
    ):
        child_env[f"AGENT_KNOWLEDGE_{env_name}"] = binding[field]
    config_dir = (_REPO / "config-service/src/main/resources/config").as_posix() + "/"
    command = [
        str(java), "-jar", str(jar), "--server.port=19201",
        "--server.address=127.0.0.1",
        "--spring.profiles.active=datasource,es,knowledge-live",
        "--spring.elasticsearch.uris=http://127.0.0.1:9200",
        "--es.query.total-hits-threshold=10000",
        "--es.query.rebuild-source-allowed-hosts[0]=localhost",
        "--es.query.rebuild-max-batch-size=500",
        "--spring.cloud.config.enabled=false", "--eureka.client.enabled=false",
        f"--spring.config.additional-location=optional:file:{config_dir}",
        "--management.health.db.enabled=false",
        "--common.security.secrets.source-order[0]=environment",
        "--common.security.secrets.allow-config-values=false",
        "--common.security.secrets.fail-fast=true",
        "--common.security.secrets.jwt.active-key-id=ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.value=",
    ]
    with tempfile.TemporaryDirectory(prefix="codex-knowledge-typed-") as temporary:
        log_path = Path(temporary) / "es-query.log"
        with log_path.open("xb") as log:
            process: subprocess.Popen[bytes] | None = None
            protected_markers = (
                _SecretBytes(token.raw.encode("ascii")),
                _SecretBytes(base64.b64encode(secret.raw)),
            )
            try:
                process = subprocess.Popen(
                    command, cwd=_REPO / "es-query-service", env=child_env,
                    stdout=log, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                del secret, child_env
                with httpx.Client(trust_env=False, follow_redirects=False, timeout=2) as client:
                    deadline = time.monotonic() + 90
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            log.flush()
                            raise AssertionError(
                                "knowledge_real_typed.service_exited." + _startup_failure_kind(log_path)
                            )
                        try:
                            if client.get("http://127.0.0.1:19201/actuator/health").status_code == 200:
                                break
                        except httpx.RequestError:
                            pass
                        time.sleep(0.4)
                    else:
                        raise AssertionError("knowledge_real_typed.service_not_ready")
                yield token
            finally:
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    if process.poll() is None:
                        raise AssertionError("knowledge_real_typed.owned_process_not_stopped")
                log.flush()
                tail = b""
                with log_path.open("rb") as saved_log:
                    for chunk in iter(lambda: saved_log.read(65536), b""):
                        block = tail + chunk
                        if any(marker.raw in block for marker in protected_markers):
                            raise AssertionError("knowledge_real_typed.secret_log_leak")
                        tail = block[-max(len(marker.raw) for marker in protected_markers):]


class _FixedModel:
    def __init__(self) -> None:
        self.calls: list[tuple[ModelTaskId, str]] = []

    async def complete(self, request: StructuredModelRequest, *, call_deadline: float) -> StructuredModelResponse:
        if call_deadline <= asyncio.get_running_loop().time():
            raise AssertionError("knowledge_real_typed.model_deadline")
        self.calls.append((request.task_id, request.task_version))
        if request.task_id is ModelTaskId.ACTION_SELECTION:
            return StructuredModelResponse(
                finish_kind=StructuredFinishKind.STOP,
                content='{"capability_id":"knowledge.query"}', tool_calls=(), usage_total_tokens=0,
            )
        if request.task_id is ModelTaskId.KNOWLEDGE_REWRITE and request.task_version == "12":
            payload = json.loads(request.user_payload_json)
            if payload["question"] != _QUESTION:
                raise AssertionError("knowledge_real_typed.question_drift")
            name = INTENT_OUTPUT_NAME
            value = {"outcome": "search", "query_mode": "lookup",
                     "domains": {"tax.policy": "selected", "tax.law": "not_selected"},
                     "missing_conditions": []}
        elif request.task_id is ModelTaskId.KNOWLEDGE_SUMMARY and request.task_version == "9":
            payload = json.loads(request.user_payload_json)
            if payload["schema_version"] != 3 or payload["question"] != _QUESTION:
                raise AssertionError("knowledge_real_typed.summary_contract_drift")
            name = SUMMARY_OUTPUT_NAME
            value = {"outcome": "insufficient_evidence", "points": []}
        else:
            raise AssertionError("knowledge_real_typed.unrelated_model_task")
        return StructuredModelResponse(
            finish_kind=StructuredFinishKind.TOOL_CALLS, content=None,
            tool_calls=(StructuredToolCall(name=name, arguments_json=json.dumps(value, ensure_ascii=False)),),
            usage_total_tokens=0,
        )


class _BoundedClients:
    def __init__(self, token: str) -> None:
        self._authorization = f"Bearer {token}"
        self.calls: Counter[str] = Counter()
        self.search_paths: list[str] = []
        self.search_statuses: list[int] = []
        self.local_statuses: list[int] = []
        self.clients: list[httpx.AsyncClient] = []

    def __call__(self, base_url: str) -> httpx.AsyncClient:
        origins = {f"http://127.0.0.1:{port}": kind for kind, port in _PORTS.items()}
        kind = origins.get(base_url)
        if kind is None:
            raise AssertionError("knowledge_real_typed.origin_forbidden")

        async def check_request(request: httpx.Request) -> None:
            if (request.method != "POST" or request.url.scheme != "http"
                    or request.url.host != "127.0.0.1" or request.url.port != _PORTS[kind]
                    or request.url.path != _PATHS[kind] or request.url.query):
                raise AssertionError("knowledge_real_typed.request_forbidden")
            authorization = request.headers.get("Authorization")
            if (kind == "search" and authorization != self._authorization) or (
                kind != "search" and authorization is not None
            ):
                raise AssertionError("knowledge_real_typed.authorization_boundary")
            if self.calls[kind] >= _LIMITS[kind]:
                raise AssertionError("knowledge_real_typed.budget_exhausted")
            self.calls[kind] += 1
            if kind == "search":
                path = json.loads(request.content).get("path")
                if path not in ("keyword", "vector"):
                    raise AssertionError("knowledge_real_typed.search_path_invalid")
                self.search_paths.append(path)

        async def check_response(response: httpx.Response) -> None:
            if kind == "search":
                self.search_statuses.append(response.status_code)
            else:
                self.local_statuses.append(response.status_code)

        client = httpx.AsyncClient(
            base_url=base_url, follow_redirects=False, trust_env=False,
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=1), timeout=None,
            event_hooks={"request": [check_request], "response": [check_response]},
        )
        self.clients.append(client)
        return client


@pytest.mark.skipif(os.environ.get("KNOWLEDGE_REAL_TYPED_OPT_IN") != "1",
                    reason="requires explicit read-only real typed opt-in")
@pytest.mark.asyncio
async def test_current_root_reads_isolated_real_typed_without_external_model(monkeypatch: pytest.MonkeyPatch) -> None:
    binding = _binding()
    _preflight(binding)
    model = _FixedModel()
    business_calls = 0

    async def forbid_business(self: HttpxBusinessDomainTransport, request: object) -> object:
        nonlocal business_calls
        business_calls += 1
        raise AssertionError("knowledge_real_typed.business_forbidden")

    monkeypatch.setattr(HttpxBusinessDomainTransport, "send", forbid_business)
    environ = {
        "AGENT_MODEL_PROVIDER": "stub", "AGENT_KNOWLEDGE_ENABLED": "true",
        "AGENT_KNOWLEDGE_ENABLED_DOMAINS": "tax.policy,tax.law",
        "AGENT_KNOWLEDGE_ES_BASE_URL": "http://127.0.0.1:19201",
        "AGENT_KNOWLEDGE_EMBEDDING_BASE_URL": "http://127.0.0.1:8908",
        "AGENT_KNOWLEDGE_RERANK_BASE_URL": "http://127.0.0.1:8909",
    }
    with _isolated_es_service(binding) as token:
        clients = _BoundedClients(token.raw)
        runtime: ModelContextBindingRuntimeInvoker | None = None
        try:
            built = build_runtime(environ, model_transport=model, knowledge_http_client_factory=clients)
            if not isinstance(built, ModelContextBindingRuntimeInvoker):
                raise AssertionError("knowledge_real_typed.current_root_not_built")
            runtime = built
            base_scope = scope(_QUESTION, deadline_monotonic=asyncio.get_running_loop().time() + 40)
            request_scope = RequestExecutionScope(context=replace(
                base_scope.context, user_token=OpaqueUserToken.from_raw(token.raw),
            ))
            outcome = await runtime.ainvoke(question=_QUESTION, scope=request_scope)
        finally:
            if runtime is not None:
                await runtime.aclose()
            for client in clients.clients:
                await client.aclose()

    assert len(clients.clients) == 3 and all(client.is_closed for client in clients.clients)
    counts = (clients.calls["embed"], clients.calls["search"], clients.calls["rerank"])
    assert clients.calls["embed"] == 1 and clients.calls["search"] == 2, (
        f"knowledge_real_typed.path_counts:{counts};paths={clients.search_paths};"
        f"search_statuses={clients.search_statuses};local_statuses={clients.local_statuses};"
        f"outcome={outcome.status.value}"
    )
    assert clients.calls["rerank"] <= 1 and clients.search_statuses == [200, 200]
    assert Counter(clients.search_paths) == Counter(("keyword", "vector"))
    assert model.calls[:2] == [(ModelTaskId.ACTION_SELECTION, "action-selection-v4"),
                               (ModelTaskId.KNOWLEDGE_REWRITE, "12")]
    assert all(task is not ModelTaskId.BUSINESS_QUERY_PLAN for task, _ in model.calls)
    assert business_calls == 0
    assert outcome.status in {CapabilityStatus.SUCCESS, CapabilityStatus.NO_RESULT,
                              CapabilityStatus.MODEL_EGRESS_DENIED}
