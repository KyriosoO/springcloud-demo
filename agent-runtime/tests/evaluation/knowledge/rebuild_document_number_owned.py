"""Private owned resources for a future independently authorized comparison.

No CLI, default run, credential discovery, alias writer, or authorization is
provided. Callers must validate the new frozen grant before opening resources.
Tests replace process/client/native-port seams; they never start real services.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from hashlib import sha256
import re
import subprocess
from typing import Protocol

import httpx

from agent_runtime.knowledge.retrieval.http import build_knowledge_http_client
from tests.evaluation.knowledge import rebuild_b_local_runner as shared
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, CleanupReport
from tests.evaluation.knowledge.rebuild_document_number_projection import ProjectedJavaPair, _safe_env


@dataclass(frozen=True, slots=True)
class ReadBinding:
    read_alias: str
    index_name: str
    index_uuid: str
    mapping_version: str

    def __post_init__(self) -> None:
        p.require(all(type(value) is str and re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value) is not None
                      for value in (self.read_alias, self.index_name, self.index_uuid, self.mapping_version)),
                  "owned_binding_invalid")
        # Dot segments are normalized by HTTP clients; _all is an ES-wide
        # selector, not an exact bound alias/index. Keep legitimate .hidden.
        p.require(self.read_alias not in (".", "..", "_all")
                  and self.index_name not in (".", "..", "_all"), "owned_binding_invalid")

    def profile_snapshot(self, domain: str) -> str:
        self.__post_init__()
        p.require(domain in ("tax.policy", "tax.law"), "owned_profile_invalid")
        profile = {"tax.policy": "tax-policy-v1", "tax.law": "tax-law-v1"}[domain]
        return sha256("\n".join((profile, self.index_name, self.index_uuid,
            "tax-knowledge-search-v1", self.mapping_version)).encode()).hexdigest()


class OwnedProxy(Protocol):
    port: int
    @property
    def closed(self) -> bool: ...
    def close(self) -> None: ...


def java_args(*, pair: ProjectedJavaPair, arm: str, binding: ReadBinding,
              port: int, proxy_port: int) -> list[str]:
    p.require(arm in p.ARMS, "owned_arm_invalid")
    binding.__post_init__()
    pair.verify_artifacts()
    index = p.ARMS.index(arm)
    config = pair.configs[index]
    # Actual frozen configuration files, not a sibling checkout or installed
    # service config. This check also binds all three shared runtime YAMLs.
    verified, _ = shared._frozen_runtime_config_dir(pair.jars[index], pair.draft.frozen_head)
    p.require(verified == config.resolve(), "owned_config_drift")
    args = [str(pair.java), "-jar", str(pair.jars[index]), f"--server.port={port}",
        "--server.address=127.0.0.1", "--spring.profiles.active=datasource,es,knowledge-live",
        "--spring.cloud.config.enabled=false", "--spring.cloud.discovery.enabled=false",
        "--eureka.client.enabled=false", f"--spring.config.additional-location={config.as_uri()}/",
        f"--spring.elasticsearch.uris=http://127.0.0.1:{proxy_port}",
        "--management.endpoint.health.probes.enabled=true",
        "--management.endpoint.health.group.knowledge-validation.include=readinessState",
        "--common.security.secrets.source-order[0]=environment",
        "--common.security.secrets.allow-config-values=false", "--common.security.secrets.fail-fast=true",
        "--common.security.secrets.jwt.active-key-id=ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.value=",
        "--es.query.knowledge.b-isolation-fixed-target=false"]
    for profile in ("tax-policy-v1", "tax-law-v1"):
        snapshot = binding.profile_snapshot({"tax-policy-v1": "tax.policy", "tax-law-v1": "tax.law"}[profile])
        for key, value in (("read-alias", binding.read_alias), ("expected-index-name", binding.index_name),
                           ("expected-index-uuid", binding.index_uuid), ("mapping-version", binding.mapping_version),
                           ("index-snapshot-id", snapshot)):
            args.append(f"--es.query.knowledge.profiles.{profile}.{key}={value}")
    return args


class OwnedJavaResources:
    """Track actual handles immediately; clean before the JAR lease can exit.

    A proxy must be registered BEFORE its start method, so partial startup can
    also be cleaned. No unknown listener is stopped, and cleanup is not retried.
    """
    def __init__(self, *, pair: ProjectedJavaPair, journal: AttemptJournal,
                 ports: tuple[int, int, int, int]) -> None:
        p.require(type(pair) is ProjectedJavaPair and type(journal) is AttemptJournal
                  and pair.resources_released and not journal.ledger.view()["stopped"]
                  and journal.ledger.view()["pending"] == 0, "owned_resources_invalid")
        # Uses only local bind probes, never terminates a pre-existing service.
        shared._port_guard(ports)
        self.pair, self.journal, self.ports = pair, journal, ports
        self.processes: dict[str, subprocess.Popen[bytes]] = {}
        self.proxies: list[OwnedProxy] = []
        self.clients: list[httpx.AsyncClient] = []
        self.backends: list[httpx.Client] = []
        self.closed = False
        self.pair.resources_released = False

    def add_proxy(self, proxy: OwnedProxy) -> None:
        p.require(not self.closed and proxy.port in self.ports[2:]
                  and proxy.port not in {item.port for item in self.proxies}, "owned_proxy_invalid")
        self.proxies.append(proxy)

    def open_client(self, port: int) -> httpx.AsyncClient:
        p.require(not self.closed and port in (*self.ports[:2], 8908, 8909), "owned_client_invalid")
        client = build_knowledge_http_client(f"http://127.0.0.1:{port}")
        self.clients.append(client)
        return client

    def open_backend(self) -> httpx.Client:
        p.require(not self.closed, "owned_resources_closed")
        client = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                              follow_redirects=False, timeout=5.0)
        self.backends.append(client)
        return client

    def start_java(self, arm: str, *, binding: ReadBinding, secret: bytes) -> subprocess.Popen[bytes]:
        p.require(not self.closed and arm in p.ARMS and arm not in self.processes
                  and type(secret) is bytes and len(secret) == 48,
                  "owned_start_invalid")
        number = p.ARMS.index(arm)
        p.require(any(proxy.port == self.ports[number + 2] and not proxy.closed for proxy in self.proxies),
                  "owned_proxy_missing")
        args = java_args(pair=self.pair, arm=arm, binding=binding,
                         port=self.ports[number], proxy_port=self.ports[number + 2])
        # Java's ConfigSecretMaterialProvider uses standard Base64, while JWT
        # signing consumes the same raw bytes. Never mix URL-safe secret text.
        environment = {**_safe_env(), "COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": base64.b64encode(secret).decode("ascii")}
        process: subprocess.Popen[bytes] | None = None
        failed = False
        try:
            process = subprocess.Popen(args, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            failed = True
        if failed:
            raise p.ProtocolError("owned_start_failed")
        assert process is not None
        self.processes[arm] = process  # Register before any readiness/next acquisition.
        return process

    def require_listeners(self) -> None:
        p.require(not self.closed and set(self.processes) == set(p.ARMS), "owned_listeners_invalid")
        for arm, port in zip(p.ARMS, self.ports[:2], strict=True):
            process = self.processes[arm]
            p.require(process.poll() is None and shared._listener_owner(port) == process.pid,
                      "owned_listener_changed")

    async def close(self) -> CleanupReport:
        p.require(not self.closed, "owned_resources_closed")
        self.closed = True
        failed = False
        try:
            self.journal.ledger.abort()
        except p.ProtocolError:
            failed = True  # Evidence failure must not prevent resource cleanup.
        processes_ok = False
        try:
            processes_ok = shared._stop_owned(list(self.processes.values()))
        except Exception:
            failed = True
        proxies_ok = True
        for proxy in reversed(self.proxies):
            try:
                proxy.close()
                proxies_ok = proxy.closed and proxies_ok
            except Exception:
                proxies_ok = False
        clients_ok = True
        for client in reversed(self.clients):
            try:
                await asyncio.wait_for(client.aclose(), timeout=5)
                clients_ok = client.is_closed and clients_ok
            except (Exception, asyncio.CancelledError):
                clients_ok = False
        for backend in reversed(self.backends):
            try:
                backend.close()
                clients_ok = backend.is_closed and clients_ok
            except Exception:
                clients_ok = False
        ports_ok = False
        try:
            shared._port_guard(self.ports)
            ports_ok = True
        except Exception:
            pass
        report = CleanupReport(processes_ok, clients_ok, proxies_ok, ports_ok)
        # Retain the unique build directory if any resource is not proven closed.
        self.pair.resources_released = all((processes_ok, clients_ok, proxies_ok, ports_ok))
        try:
            self.journal.seal_cleanup(report)
        except p.ProtocolError:
            failed = True
        if failed or not self.pair.resources_released:
            raise p.ProtocolError("owned_cleanup_failed") from None
        return report

    async def __aenter__(self) -> OwnedJavaResources:
        p.require(not self.closed, "owned_resources_closed")
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
