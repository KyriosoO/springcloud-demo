"""Owned local read-only service lifecycle for Stage B validation, no model access."""
from __future__ import annotations

import base64
from contextlib import contextmanager
import json
import os
import re
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time

import httpx

REPO = Path(__file__).resolve().parents[3]


def stop_owned(processes):
    """Attempt every owned PID even if an earlier process does not exit promptly."""
    for process in reversed(processes):
        try:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            continue
    return all(process.poll() is not None for process in processes)


@contextmanager
def local_services(emit, *, include_agent=False):
    for port in ((18090, 19201, 18080) if include_agent else (18090, 19201)):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    binding = json.loads((REPO / "serviceCenter/knowledge-runtime-binding.v1.json").read_text(encoding="utf-8-sig"))
    classes = REPO / "es-query-service/target/classes"
    classpath = (REPO / "es-query-service/target/stage-b-classpath.txt").read_text(encoding="utf-8").strip()
    secret = base64.b64encode(secrets.token_bytes(48)).decode()
    updates = {"COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE": secret}
    for env_name, key in (("READ_ALIAS", "readAlias"), ("EXPECTED_INDEX_NAME", "expectedIndexName"),
                          ("EXPECTED_INDEX_UUID", "expectedIndexUuid"), ("MAPPING_VERSION", "mappingVersion"),
                          ("POLICY_SNAPSHOT_ID", "policySnapshotId"), ("LAW_SNAPSHOT_ID", "lawSnapshotId")):
        updates["AGENT_KNOWLEDGE_" + env_name] = binding[key]
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    processes, streams = [], []
    token = ""
    try:
        with tempfile.TemporaryDirectory(prefix="codex-kstage-b-services-") as directory:
            run_root = Path(directory)
            try:
                common = ["--spring.cloud.config.enabled=false",
                          "--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
                          "--eureka.client.enabled=false", "--common.security.secrets.source-order[0]=environment",
                          "--common.security.secrets.allow-config-values=false", "--common.security.secrets.fail-fast=true",
                          "--common.security.secrets.jwt.active-key-id=ACTIVE",
                          "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
                          "--common.security.secrets.jwt.keys.ACTIVE.value="]
                launches = (
                    ("auth-service", 18090, ["-jar", str(REPO / "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar")], []),
                    ("es-query-service", 19201, ["-cp", str(classes) + os.pathsep + classpath,
                         "com.dylan.esquery.EsQueryServiceApplication"],
                     ["--spring.profiles.active=datasource,es,knowledge-live", "--spring.elasticsearch.uris=http://127.0.0.1:9200",
                      "--es.query.total-hits-threshold=10000", "--es.query.rebuild-source-allowed-hosts[0]=localhost",
                      "--es.query.rebuild-max-batch-size=500"]),
                )
                if include_agent:
                    agent_classpath = (REPO / "agent-service/target/stage-b-classpath.txt").read_text(encoding="utf-8").strip()
                    launches += (("agent-service", 18080,
                        ["-cp", str(REPO / "agent-service/target/classes") + os.pathsep + agent_classpath,
                         "com.dylan.agent.service.AgentServiceApplication"],
                        ["--spring.main.web-application-type=reactive", "--spring.config.import=",
                         "--agent.runtime.base-url=http://127.0.0.1:19091", "--agent.runtime.contract-version=1"]),)
                for module, port, command, extra in launches:
                    stream = (run_root / f"{module}.log").open("xb")
                    streams.append(stream)
                    processes.append(subprocess.Popen(
                        ["java", *command, f"--server.port={port}", *common, *extra], cwd=REPO / module,
                        env={**{key: os.environ[key] for key in (
                            "SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP", "USERPROFILE",
                            "APPDATA", "LOCALAPPDATA", "JAVA_TOOL_OPTIONS") if key in os.environ}, **updates},
                        stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW))
                with httpx.Client(trust_env=False, follow_redirects=False, timeout=3) as client:
                    # Agent readiness is checked by the caller after Runtime starts.
                    for process, url in zip(processes[:2], ("http://127.0.0.1:18090/public/test", "http://127.0.0.1:19201/actuator/health"), strict=True):
                        deadline = time.monotonic() + 90
                        while time.monotonic() < deadline:
                            if process.poll() is not None:
                                raise RuntimeError("stage_b.service_exited")
                            try:
                                if client.get(url).status_code == 200:
                                    break
                            except httpx.HTTPError:
                                pass
                            time.sleep(0.5)
                        else:
                            raise RuntimeError("stage_b.readiness_timeout")
                    alias = client.get(f"http://127.0.0.1:9200/_alias/{binding['readAlias']}")
                    alias.raise_for_status()
                    if list(alias.json()) != [binding["expectedIndexName"]]:
                        raise RuntimeError("stage_b.index_binding_changed")
                    settings = client.get(f"http://127.0.0.1:9200/{binding['expectedIndexName']}/_settings",
                                          params={"filter_path": "*.settings.index.uuid"})
                    settings.raise_for_status()
                    if settings.json()[binding["expectedIndexName"]]["settings"]["index"]["uuid"] != binding["expectedIndexUuid"]:
                        raise RuntimeError("stage_b.index_uuid_changed")
                    response = client.post("http://127.0.0.1:18090/login", json={"userId": "admin", "password": "123456"})
                    response.raise_for_status()
                    token = client.cookies.get("AUTH_TOKEN") or ""
                    if not token:
                        raise RuntimeError("stage_b.auth_token_missing")
                yield token, binding
            finally:
                stopped = stop_owned(processes)
                for stream in streams:
                    stream.close()
                leaked = False
                for log in run_root.glob("*.log"):
                    raw = log.read_bytes()
                    if any(process.returncode not in (None, 0, 1, 143) for process in processes) or b"APPLICATION FAILED TO START" in raw or b"Exception" in raw:
                        text = raw.decode("utf-8", errors="replace")
                        emit({"stage": "startup_diagnostic", "service": log.stem,
                              "exceptionClasses": sorted(set(re.findall(r"(?:Caused by: |Exception in thread \"main\" )([A-Za-z0-9_.$]+)", text))),
                              "markers": [marker for marker in ("APPLICATION FAILED TO START", "Could not find or load main class", "NoSuchMethodError", "Could not resolve placeholder", "Failed to bind properties", "knowledge.profile") if marker in text]})
                    leaked |= secret.encode() in raw or bool(token and token.encode() in raw)
                    if log.resolve().parent != run_root.resolve():
                        raise RuntimeError("stage_b.cleanup_path_invalid")
                    log.unlink()
                emit({"stage": "cleanup", "ownedProcessesStopped": stopped,
                      "rawLogsDeleted": True, "secretScanPassed": not leaked})
                if leaked or not stopped:
                    raise RuntimeError("stage_b.cleanup_failed")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
