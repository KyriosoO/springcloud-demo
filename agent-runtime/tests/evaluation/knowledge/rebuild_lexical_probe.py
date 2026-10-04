"""Private one-shot old/new lexical diagnosis, not a B or MEASURE runner.

Same frozen archive/config/index; only DocumentNumberQuery.java differs. All
public bodies and temporary credentials stay in memory. No inference or writes.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from hashlib import sha256
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import tempfile
from threading import Lock, Thread
import time
from typing import Any, Iterator
from zipfile import ZipFile

import httpx

from agent_runtime.knowledge.contracts import RetrievalPath
from agent_runtime.knowledge.retrieval.contracts import KnowledgePathRequest, PathResultKind
from agent_runtime.knowledge.retrieval.es_adapter import EsKnowledgeSearchAdapter
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, BoundedHttpResponse
from tests.evaluation.knowledge import rebuild_b_local_runner as shared

ROOT = shared.ROOT
OLD_HEAD = "a1ba290e8b2d78da71d46bc1f39018be502c7347"
HELPER = "es-query-service/src/main/java/com/dylan/esquery/service/DocumentNumberQuery.java"
FIXTURE = "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json"
FIXTURE_SHA = "04a437d215ab242ea5e69eed95d109f47cf617135778f4d2cf5a13f6cddce26a"
SOURCE = "agent-runtime/tests/uat/knowledge-rebuild-measure-20261003-01/manifest.json"
SOURCE_SHA = "47dee2d00fdd980fb0280c269b5f390d4ba3febc9bfc7bdcd4dcf69190d5fcd8"
RUN_ID = "knowledge-lexical-probe-20261004-01"
DIRECTORY = ROOT / "knowledge-corpus-tools/evidence" / RUN_ID
CASE_IDS = ("UAT-KM-001", "UAT-KM-002", "UAT-KM-003", "UAT-KM-012")
PORTS = (19221, 19222, 19321, 19322)
LIMITS = {"typed": 8, "search": 8, "metadata": 18, "health": 40}
_MAX = 2 * 1024 * 1024
_ENV = ("SystemRoot", "SystemDrive", "PATH", "JAVA_HOME", "TEMP", "TMP",
        "USERPROFILE", "APPDATA", "LOCALAPPDATA")
_CATEGORIES = ["税务规范性文件", "财税文件", "工作通知", "其他文件", "政策解读",
               "税务部门规章", "国务院文件", "curated"]
_SOURCE_FIELDS = sorted(["documentId", "chunkId", "title", "content", "sourceUrl",
                         "documentNo", "writtenDate", "materialType", "aclRef"])


class ProbeError(ValueError):
    """Only finite reason codes; never embed response bodies or exceptions."""


class _NoSend:
    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        raise ProbeError("unexpected_adapter_send")


def require(condition: bool, reason: str = "input_invalid") -> None:
    if not condition:
        raise ProbeError(reason)


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def decode(raw: bytes) -> dict[str, Any]:
    require(0 < len(raw) <= _MAX)
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            require(key not in value, "json_duplicate")
            value[key] = item
        return value

    def constant(_: str) -> None:
        raise ProbeError("json_nonfinite")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=constant)
        require(type(result) is dict)
        return dict(result)
    except (ValueError, UnicodeError):
        raise ProbeError("json_invalid") from None


def write_once(path: Path, value: object) -> None:
    with path.open("xb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def safe_env() -> dict[str, str]:
    # Deliberately never read or inherit LLM_API_KEY/JWT/Java injection variables.
    return {key: os.environ[key] for key in _ENV if key in os.environ}


def prepare_spec(head: str) -> dict[str, Any]:
    require(shared._git("branch", "--show-current") == "codex_0915", "branch_invalid")
    require(shared._git("rev-parse", "HEAD") == head and not
            shared._git("status", "--porcelain", "--untracked-files=no"), "code_drift")
    raw = shared._git_bytes("show", f"{head}:{FIXTURE}")
    source = shared._git_bytes("show", f"{head}:{SOURCE}")
    require(sha256(raw).hexdigest() == FIXTURE_SHA and sha256(source).hexdigest() == SOURCE_SHA,
            "source_drift")
    fixture, original = decode(raw), decode(source)
    cases = [item for case_id in CASE_IDS for item in fixture["cases"] if item["caseId"] == case_id]
    require(len(cases) == 4)
    # All other production Java, reactor dependencies and launch configuration
    # must still be identical to the helper's old-source commit.
    changed = shared._git("diff", "--name-only", OLD_HEAD, head, "--",
        "es-query-service/src/main", "es-query-service/pom.xml", "es-query-api",
        "common-security", "serviceCenter/pom.xml", shared._RUNTIME_CONFIG_ROOT).splitlines()
    require(changed == [HELPER], "single_variable_unproven")
    previous = original["indexBindings"]["tax.policy"]
    bindings = {key: previous[key] for key in ("readAlias", "indexName", "indexUuid",
                                               "mappingVersion", "mappingSha256")}
    bindings["policySnapshot"] = previous["snapshotId"]
    require(bindings["indexName"] == "agent-doc-tax-policy-v5-20260907-vector-b2")
    return {"schemaVersion": 1, "runId": RUN_ID, "branch": "codex_0915", "frozenHead": head,
        "authorization": "human-confirmed-20261004-exact-8-18-40",
        "oldHelperSourceHead": OLD_HEAD,
        "helperSha256": {arm: sha256(shared._git_bytes("show", f"{commit}:{HELPER}")).hexdigest()
                         for arm, commit in (("old", OLD_HEAD), ("current", head))},
        "fixtureSha256": FIXTURE_SHA, "sourceMetadataSha256": SOURCE_SHA,
        "binding": bindings, "aliasFlags": original["aliasFlags"],
        "cases": [{"caseId": item["caseId"], "question": item["question"],
                   "necessarySources": item["necessarySources"]} for item in cases],
        "sources": [item for item in fixture["sources"]
                    if any(item["id"] in case["necessarySources"] for case in cases)],
        "limits": LIMITS, "ports": list(PORTS), "topK": 20, "domain": "tax.policy",
        "profile": "tax-policy-v1", "path": "keyword", "runtimeConfigSha256":
        shared._frozen_runtime_config_hashes(head),
        "forbidden": {key: 0 for key in ("model", "embedding", "rerank", "writes", "retry", "resume")},
        "scope": "current-keyword-diagnosis-only;not-UAT-not-full-record-snapshot"}


class Ledger:
    def __init__(self, directory: Path) -> None:
        self.counts = dict.fromkeys(LIMITS, 0)
        self.events: list[dict[str, object]] = []
        self.lock = Lock()
        self.stream = (directory / "journal.jsonl").open("xb")

    def reserve(self, kind: str, label: str, digest: str | None = None) -> None:
        with self.lock:
            require(kind in LIMITS and self.counts[kind] < LIMITS[kind], "budget_exceeded")
            self.counts[kind] += 1
            event = {"sequence": len(self.events) + 1, "kind": kind, "label": label,
                     "requestSha256": digest}
            self.stream.write(canonical(event) + b"\n")
            self.stream.flush()
            os.fsync(self.stream.fileno())
            self.events.append(event)

    def close(self) -> None:
        self.stream.close()


def bounded(client: httpx.Client, method: str, path: str, body: bytes = b"",
            headers: dict[str, str] | None = None, *, health: bool = False
            ) -> tuple[int, str, bytes, str | None]:
    with client.stream(method, path, content=body or None,
                       headers={"Accept-Encoding": "identity", "Content-Type": "application/json",
                                **(headers or {})}, timeout=5, follow_redirects=False) as response:
        require(response.headers.get("content-encoding", "identity") == "identity", "encoding_invalid")
        product = response.headers.get_list("x-elastic-product")
        require(len(product) <= 1 and (not product or product[0] == "Elasticsearch"), "product_invalid")
        media = response.headers.get("content-type", "").split(";", 1)[0].strip()
        allowed_media = {"application/json", "application/vnd.spring-boot.actuator.v3+json"} if health else {"application/json"}
        require(media in allowed_media, "media_invalid")
        result = bytearray()
        deadline = time.monotonic() + 10
        for chunk in response.iter_bytes():
            require(time.monotonic() <= deadline, "response_deadline_exceeded")
            require(len(result) + len(chunk) <= _MAX, "response_too_large")
            result.extend(chunk)
        return response.status_code, media, bytes(result), product[0] if product else None


def metadata_paths(spec: dict[str, Any]) -> tuple[str, str, str]:
    binding = spec["binding"]
    return (f'/_alias/{binding["readAlias"]}', f'/{binding["indexName"]}/_settings',
            f'/{binding["indexName"]}/_mapping')


def attest_metadata(es: httpx.Client, ledger: Ledger, spec: dict[str, Any], phase: str) -> dict[str, object]:
    values = []
    for path in metadata_paths(spec):
        ledger.reserve("metadata", f"{phase}:{path}")
        status, _, raw, _ = bounded(es, "GET", path)
        require(status == 200, "metadata_http_failed")
        values.append(decode(raw))
    alias, settings, mapping = values
    b = spec["binding"]
    name = b["indexName"]
    require(set(alias) == {name} and alias[name]["aliases"][b["readAlias"]] == spec["aliasFlags"],
            "alias_drift")
    require(set(settings) == {name} and settings[name]["settings"]["index"]["uuid"] == b["indexUuid"],
            "index_drift")
    require(set(mapping) == {name} and mapping[name]["mappings"]["_meta"]["mapping_version"]
            == b["mappingVersion"], "mapping_drift")
    fingerprint = sha256(canonical(mapping[name]["mappings"]) + b"\n").hexdigest()
    require(fingerprint == b["mappingSha256"], "mapping_drift")
    return {"phase": phase, "indexUuid": b["indexUuid"], "mappingSha256": fingerprint,
            "aliasFlags": spec["aliasFlags"], "fullRecordFingerprint": "not_observed"}


def expected_physical(question: str, arm: str, ordinal: int) -> dict[str, object]:
    """Exact fixed public probes, not a planner or gold-derived query."""
    multi: dict[str, object] = {"multi_match": {"query": question, "fields": ["title", "content", "section"]}}
    filtered = [{"terms": {"channel": _CATEGORIES}}]
    # Freeze the two helpers' already verified local output for these original
    # questions. This validates the physical request, never adds a retrieval call.
    ref = ("财税〔2016〕36号" if ordinal == 0 else
           ("税务总局公告2022年第13号" if arm == "old" else "财政部税务总局公告2022年第13号")
           if ordinal == 2 else None)
    if ref is None:
        query: dict[str, object] = {"bool": {"filter": filtered, "must": [multi]}}
    else:
        pattern = "[ 　]*".join(ref)
        query = {"bool": {"filter": filtered, "should": [multi,
            {"constant_score": {"filter": {"bool": {"should": [
                {"regexp": {"documentNo": {"value": pattern, "flags": "NONE",
                                      "case_insensitive": False, "max_determinized_states": 256}}}],
                "minimum_should_match": 1}}, "boost": 100}}], "minimum_should_match": 1}}
    return {"_source": {"includes": _SOURCE_FIELDS}, "track_total_hits": False, "size": 21, "query": query}


class ProbeProxy:
    def __init__(self, spec: dict[str, Any], arm: str, port: int, ledger: Ledger, es: httpx.Client) -> None:
        self.spec, self.arm, self.port, self.ledger, self.es = spec, arm, port, ledger, es
        self.lock = Lock()
        self.metadata = dict.fromkeys(metadata_paths(spec), 0)
        self.expected: int | None = None
        self.completed = 0
        self.violations = 0
        self.server: ThreadingHTTPServer | None = None
        self.thread: Thread | None = None

    def expect(self, ordinal: int) -> None:
        with self.lock:
            require(self.expected is None and ordinal == self.completed and self.violations == 0,
                    "search_sequence_invalid")
            self.expected = ordinal

    def forward(self, method: str, path: str, body: bytes) -> tuple[int, str, bytes, str | None]:
        with self.lock:
            if method == "GET" and path in self.metadata and not body:
                require(self.metadata[path] < 2, "startup_metadata_repeated")
                self.metadata[path] += 1
                self.ledger.reserve("metadata", f"{self.arm}:{path}")
            elif method == "POST" and path == f'/{self.spec["binding"]["readAlias"]}/_search':
                require(self.expected is not None and self.completed < 4, "search_not_expected")
                ordinal = self.expected
                assert ordinal is not None
                expected = expected_physical(self.spec["cases"][ordinal]["question"], self.arm, ordinal)
                require(canonical(decode(body)) == canonical(expected), "physical_query_invalid")
                self.expected = None  # A retry cannot reach ES even if the first response fails.
                self.completed += 1
                self.ledger.reserve("search", f'{self.arm}:{self.spec["cases"][ordinal]["caseId"]}',
                                    sha256(body).hexdigest())
            else:
                raise ProbeError("proxy_route_forbidden")
        return bounded(self.es, method, path, body)

    def start(self) -> None:
        owner = self

        class Server(ThreadingHTTPServer):
            daemon_threads = False
            block_on_close = True

        class Handler(BaseHTTPRequestHandler):
            def setup(self) -> None:
                super().setup()
                self.connection.settimeout(6)

            def log_message(self, format: str, *args: object) -> None:
                return

            def do_GET(self) -> None:
                self.handle_forward("GET")

            def do_POST(self) -> None:
                self.handle_forward("POST")

            def do_PUT(self) -> None:
                self.handle_forward("PUT")

            def do_DELETE(self) -> None:
                self.handle_forward("DELETE")

            def handle_forward(self, method: str) -> None:
                try:
                    lengths = self.headers.get_all("Content-Length", [])
                    require(len(lengths) <= 1 and not self.headers.get_all("Transfer-Encoding"), "length_invalid")
                    length = lengths[0] if lengths else "0"
                    require(length.isascii() and length.isdecimal() and int(length) <= _MAX, "length_invalid")
                    remaining = int(length)
                    request_deadline = time.monotonic() + 6
                    received = bytearray()
                    while remaining:
                        timeout = request_deadline - time.monotonic()
                        require(timeout > 0, "request_deadline_exceeded")
                        self.connection.settimeout(timeout)
                        chunk = self.rfile.read1(min(remaining, 65536))
                        require(bool(chunk), "body_incomplete")
                        received.extend(chunk)
                        remaining -= len(chunk)
                    body = bytes(received)
                    self.connection.settimeout(6)
                    require(len(body) == int(length), "body_incomplete")
                    status, media, data, product = owner.forward(method, self.path, body)
                    self.send_response(status)
                    self.send_header("Content-Type", media)
                    self.send_header("Content-Length", str(len(data)))
                    if product is not None:
                        self.send_header("X-Elastic-Product", product)
                    self.end_headers()
                    self.wfile.write(data)
                except Exception:
                    with owner.lock:
                        owner.violations += 1
                    try:
                        self.send_error(502)
                    except OSError:
                        pass

        self.server = Server(("127.0.0.1", self.port), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self) -> None:
        if self.server is not None:
            if self.thread is not None and self.thread.is_alive():
                self.server.shutdown()
            self.server.server_close()
        if self.thread is not None and self.thread.ident is not None:
            self.thread.join(timeout=6)
            require(not self.thread.is_alive(), "proxy_cleanup_failed")


def extract_archive(raw: bytes, root: Path) -> None:
    require(0 < len(raw) <= 512 * 1024 * 1024, "archive_invalid")
    with ZipFile(BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(sum(item.file_size for item in entries) <= 1024 * 1024 * 1024
                and len({item.filename for item in entries}) == len(entries), "archive_invalid")
        for item in entries:
            require((root / item.filename).resolve().is_relative_to(root.resolve()) and
                    item.file_size <= 256 * 1024 * 1024 and
                    not stat.S_ISLNK(item.external_attr >> 16), "archive_invalid")
        archive.extractall(root)


def java_projection(jar: Path, spec: dict[str, Any], arm: str) -> list[str]:
    """Offline actual Java body builder + frozen YAML; no RestClient created.

    The finite inspector is compiled into the temporary build directory, then
    uses the same application class loader as the package-private body builder.
    It starts no server, inference, or network transport.
    """
    root = jar.parent / "lexical-offline-projection"
    root.mkdir()
    extract_archive(jar.read_bytes(), root)
    source = root / "LexicalProjection.java"
    source.write_text('''package com.dylan.esquery.service;
import java.util.*;
import java.nio.charset.StandardCharsets;
import org.springframework.beans.factory.config.YamlPropertiesFactoryBean;
import org.springframework.core.io.FileSystemResource;
import org.springframework.boot.context.properties.bind.*;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.fasterxml.jackson.databind.ObjectMapper;
public class LexicalProjection {
 public static void main(String[] args) throws Exception {
  var yaml = new YamlPropertiesFactoryBean();
  yaml.setResources(new FileSystemResource(args[0]));
  var props = Objects.requireNonNull(yaml.getObject());
  var profile = new Binder(new MapConfigurationPropertySource(props)).bind(
    "es.query.knowledge.profiles.tax-policy-v1", Bindable.of(KnowledgeSearchProfile.class)).get();
  var mapper = new ObjectMapper();
  var service = new KnowledgeSearchService(null, mapper, new KnowledgeSearchProperties());
  for (int i=1; i<args.length; i++) {
   var request = new KnowledgeSearchRequest(1,"tax.policy","tax-policy-v1","keyword",args[i],null,20);
   System.out.write(mapper.writeValueAsString(service.buildSearchBody(request,profile)).getBytes(StandardCharsets.UTF_8));
   System.out.write(10);
  }
 }
}
''', encoding="utf-8")
    classpath = os.pathsep.join((str(root / "BOOT-INF/classes"), str(root / "BOOT-INF/lib/*")))
    java = shared._java_runtime_executable()
    javac = Path(java).with_name("javac.exe" if os.name == "nt" else "javac")
    require(javac.is_file(), "java_projection_compiler_unavailable")
    classes = root / "inspector-classes"
    classes.mkdir()
    compiled = subprocess.run([str(javac), "-encoding", "UTF-8", "-cp", classpath,
        "-d", str(classes), str(source)], env=safe_env(), stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, timeout=45, check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(compiled.returncode == 0, "java_projection_compile_failed")
    command = [java, "-Dfile.encoding=UTF-8", "-cp", str(classes) + os.pathsep + classpath,
        "com.dylan.esquery.service.LexicalProjection",
        str(root / "BOOT-INF/classes/application-knowledge-live.yml"),
        *(case["question"] for case in spec["cases"])]
    inspected = subprocess.run(command, env=safe_env(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=45, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    require(inspected.returncode == 0 and 0 < len(inspected.stdout) <= 65536, "java_projection_failed")
    lines = inspected.stdout.splitlines()
    require(len(lines) == 4, "java_projection_failed")
    for ordinal, line in enumerate(lines):
        require(canonical(decode(line)) == canonical(expected_physical(spec["cases"][ordinal]["question"], arm, ordinal)),
                "java_projection_mismatch")
    return [sha256(canonical(decode(line))).hexdigest() for line in lines]


@contextmanager
def artifacts(spec: dict[str, Any], directory: Path) -> Iterator[list[tuple[Path, Path]]]:
    archive = shared._git_bytes("archive", "--format=zip", spec["frozenHead"])
    maven = shutil.which("mvn")
    require(maven is not None and Path(maven).is_file(), "maven_unavailable")
    assert maven is not None
    attestation: dict[str, object] = {"archiveSha256": sha256(archive).hexdigest(),
        "frozenHead": spec["frozenHead"], "oldHelperSourceHead": OLD_HEAD,
        "sourceDifference": [HELPER], "helperSha256": spec["helperSha256"],
        "mavenExecutableSha256": shared._hash_file(Path(maven)), "builds": []}
    builds: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="knowledge-lexical-build-") as temporary:
        jars = []
        for arm in ("old", "current"):
            root = Path(temporary) / arm
            root.mkdir()
            extract_archive(archive, root)
            # Only this source blob is replaced. Existing target/ and services
            # are never touched, and the old repository is never checked out.
            (root / HELPER).write_bytes(shared._git_bytes("show", f'{OLD_HEAD if arm == "old" else spec["frozenHead"]}:{HELPER}'))
            command = [maven, "--offline", "--batch-mode", "-f", str(root / "serviceCenter/pom.xml"),
                       "-pl", ":es-query-service", "-am", "-DskipTests", "package"]
            built = subprocess.run(command, cwd=root / "serviceCenter", env=safe_env(),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            jar = root / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
            require(built.returncode == 0 and jar.is_file() and jar.stat().st_size > 0, "build_failed")
            config, hashes = shared._frozen_runtime_config_dir(jar, spec["frozenHead"])
            require(hashes == spec["runtimeConfigSha256"], "config_drift")
            projection = java_projection(jar, spec, arm)
            builds.append({"arm": arm, "jarSha256": shared._hash_file(jar),
                "jarBytes": jar.stat().st_size, "exitCode": 0, "testsExecutedByBuild": False,
                "offlineActualJavaRequestSha256": projection})
            jars.append((jar, config))
        attestation["builds"] = builds
        write_once(directory / "build.json", attestation)
        yield jars


def java_args(spec: dict[str, Any], jar: Path, config: Path, arm: int, java: str) -> list[str]:
    binding = spec["binding"]
    snapshots = {profile: sha256("\n".join((profile, binding["indexName"], binding["indexUuid"],
                    "tax-knowledge-search-v1", binding["mappingVersion"])).encode()).hexdigest()
                 for profile in ("tax-policy-v1", "tax-law-v1")}
    args = [java, "-jar", str(jar), f"--server.port={PORTS[arm]}", "--server.address=127.0.0.1",
        "--spring.profiles.active=datasource,es,knowledge-live", "--spring.cloud.config.enabled=false",
        "--spring.cloud.discovery.enabled=false", "--eureka.client.enabled=false",
        f"--spring.config.additional-location={config.as_uri()}/",
        f"--spring.elasticsearch.uris=http://127.0.0.1:{PORTS[arm + 2]}",
        "--management.endpoint.health.probes.enabled=true",
        "--management.endpoint.health.group.knowledge-validation.include=readinessState",
        "--common.security.secrets.source-order[0]=environment", "--common.security.secrets.allow-config-values=false",
        "--common.security.secrets.fail-fast=true", "--common.security.secrets.jwt.active-key-id=ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "--common.security.secrets.jwt.keys.ACTIVE.value=", "--es.query.knowledge.b-isolation-fixed-target=false"]
    for profile in snapshots:
        for key, value in (("read-alias", binding["readAlias"]), ("expected-index-name", binding["indexName"]),
                           ("expected-index-uuid", binding["indexUuid"]), ("mapping-version", binding["mappingVersion"]),
                           ("index-snapshot-id", snapshots[profile])):
            args.append(f"--es.query.knowledge.profiles.{profile}.{key}={value}")
    return args


def ready(process: subprocess.Popen[bytes], port: int, ledger: Ledger) -> None:
    with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, follow_redirects=False) as client:
        for _ in range(20):
            require(process.poll() is None, "java_exited")
            ledger.reserve("health", str(port))
            try:
                status, _, raw, _ = bounded(client, "GET", "/actuator/health/knowledge-validation", health=True)
                if status == 200 and decode(raw).get("status") == "UP":
                    require(shared._listener_owner(port) == process.pid, "listener_owner_invalid")
                    return
            except httpx.ConnectError:
                pass  # Only bounded, predeclared readiness polls; never search retries.
            time.sleep(2)
    raise ProbeError("readiness_exhausted")


def typed_request(spec: dict[str, Any], ordinal: int) -> KnowledgePathRequest:
    return KnowledgePathRequest(logical_domain_id="tax.policy", retrieval_profile_id="tax-policy-v1",
        path=RetrievalPath.KEYWORD, query_text=spec["cases"][ordinal]["question"],
        query_vector=None, candidate_limit=20)


def cleanup_owned(processes: list[subprocess.Popen[bytes]], proxies: list[ProbeProxy],
                  terminal: dict[str, Any]) -> None:
    terminal["cleanupAttempted"] = True
    stopped = shared._stop_owned(processes)
    for proxy in reversed(proxies):
        try:
            proxy.close()
        except Exception:
            stopped = False
    # An unrelated pre-existing listener is not ours to clean or stop.
    if processes or proxies:
        try:
            shared._port_guard(PORTS)
        except (shared.BLocalRunError, OSError):
            stopped = False
    terminal["cleanup"] = stopped


@contextmanager
def owned_lifetime(processes: list[subprocess.Popen[bytes]], proxies: list[ProbeProxy],
                   terminal: dict[str, Any]) -> Iterator[None]:
    try:
        yield
    finally:
        # This scope exits BEFORE the backend client or TemporaryDirectory.
        # Windows must release the running JAR before archive cleanup.
        cleanup_owned(processes, proxies, terminal)


def run(spec: dict[str, Any], directory: Path) -> dict[str, Any]:
    ledger = Ledger(directory)
    processes: list[subprocess.Popen[bytes]] = []
    proxies: list[ProbeProxy] = []
    rows: list[dict[str, object]] = []
    terminal: dict[str, Any] = {"schemaVersion": 1, "runId": RUN_ID, "status": "failed_unconsumed",
        "reason": "unclassified_technical_failure", "cases": rows, "metadata": [], "cleanup": False,
        "interpretation": "keyword-only-diagnosis;not-B-not-MEASURE-not-effectiveness-UAT"}
    phase = "build"
    try:
        shared._require_locked_python_environment("comparison")
        java = shared._java_runtime_executable()
        shared._port_guard(PORTS)
        with artifacts(spec, directory) as jars, httpx.Client(base_url="http://127.0.0.1:9200",
                trust_env=False, follow_redirects=False) as es, owned_lifetime(processes, proxies, terminal):
            require(prepare_spec(spec["frozenHead"]) == spec, "freeze_drift")
            write_once(directory / "consumed.json", {"runId": RUN_ID, "scope": spec["authorization"],
                "manifestSha256": sha256((directory / "manifest.json").read_bytes()).hexdigest()})
            terminal["status"] = "failed_consumed"
            phase = "pre_metadata"
            terminal["metadata"].append(attest_metadata(es, ledger, spec, "pre"))
            secret = secrets.token_bytes(48)
            env = safe_env()
            env["COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE"] = base64.b64encode(secret).decode()
            phase = "startup"
            for ordinal, (arm, (jar, config)) in enumerate(zip(("old", "current"), jars, strict=True)):
                proxy = ProbeProxy(spec, arm, PORTS[ordinal + 2], ledger, es)
                proxies.append(proxy)
                proxy.start()
                process = subprocess.Popen(java_args(spec, jar, config, ordinal, java), env=env,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                processes.append(process)
                ready(process, PORTS[ordinal], ledger)
            require(ledger.counts["metadata"] == 15 and all(proxy.violations == 0 for proxy in proxies),
                    "startup_counts_invalid")
            token = shared._jwt(secret)
            phase = "keyword"
            for arm_index, arm in enumerate(("old", "current")):
                with httpx.Client(base_url=f"http://127.0.0.1:{PORTS[arm_index]}",
                        trust_env=False, follow_redirects=False) as client:
                    for ordinal, case in enumerate(spec["cases"]):
                        process = processes[arm_index]
                        require(process.poll() is None and shared._listener_owner(PORTS[arm_index]) == process.pid,
                                "listener_owner_invalid")
                        request = typed_request(spec, ordinal)
                        body = canonical({"schemaVersion": 1, "logicalDomainId": "tax.policy",
                            "retrievalProfileId": "tax-policy-v1", "path": "keyword",
                            "queryText": request.query_text, "queryVector": None, "limit": 20})
                        proxies[arm_index].expect(ordinal)
                        ledger.reserve("typed", f'{arm}:{case["caseId"]}', sha256(body).hexdigest())
                        status, media, raw, _ = bounded(client, "POST", "/es/knowledge/search", body,
                                                      {"Authorization": f"Bearer {token}"})
                        require(status == 200, "typed_http_failed")
                        # Use the production strict response decoder, without a
                        # transport or another outbound send.
                        result = EsKnowledgeSearchAdapter(_NoSend())._decode(request, media, "identity", raw)
                        require(result.kind in (PathResultKind.CANDIDATES, PathResultKind.NO_RESULT)
                            and result.index_snapshot_id == spec["binding"]["policySnapshot"]
                            and result.read_policy_version == "tax-public-authenticated-v1"
                            and proxies[arm_index].completed == ordinal + 1
                            and proxies[arm_index].violations == 0, "typed_result_invalid")
                        projected = [{"documentId": item.document_id, "chunkId": item.chunk_id,
                                      "contentSha256": item.content_sha256, "rank": item.source_rank}
                                     for item in result.candidates]
                        sources = []
                        for source_id in case["necessarySources"]:
                            source = next(item for item in spec["sources"] if item["id"] == source_id)
                            match = next((item for item in projected if item["documentId"] == source["documentId"]
                                          and item["chunkId"] == source["chunkId"]), None)
                            require(match is None or match["contentSha256"] == source["contentSha256"], "source_hash_drift")
                            sources.append({"sourceId": source_id, "rank": match["rank"] if match else None})
                        row = {"arm": arm, "caseId": case["caseId"], "candidateCount": len(projected),
                               "truncated": result.truncated, "candidates": projected, "sources": sources}
                        rows.append(row)
                        write_once(directory / f'{arm}-{case["caseId"]}.json', row)
            phase = "post_metadata"
            terminal["metadata"].append(attest_metadata(es, ledger, spec, "post"))
            require(ledger.counts["metadata"] == 18 and ledger.counts["search"] == 8
                    and ledger.counts["typed"] == 8 and all(proxy.violations == 0 for proxy in proxies),
                    "terminal_counts_invalid")
            terminal.update(status="completed", reason=None)
    except (ProbeError, shared.BLocalRunError) as error:
        terminal["status"] = "failed_consumed" if (directory / "consumed.json").exists() else "failed_unconsumed"
        terminal["reason"] = str(error)
    except Exception:
        # Do not swallow success or retry; seal failure without leaking raw error text.
        terminal["status"] = "failed_consumed" if (directory / "consumed.json").exists() else "failed_unconsumed"
        terminal["reason"] = "unclassified_technical_failure"
    finally:
        if not terminal.get("cleanupAttempted"):
            cleanup_owned(processes, proxies, terminal)
        if not terminal["cleanup"]:
            terminal.update(status="failed_consumed" if ledger.events else "failed_unconsumed",
                            reason="cleanup_failed")
        terminal.update(phase=phase, counts=ledger.counts,
                        proxyViolations=sum(proxy.violations for proxy in proxies),
                        forbiddenActual={"model": 0, "embedding": 0, "rerank": 0, "writes": 0},
                        retryResumePolicy="disabled;any-proxy-violation-invalidates-run")
        if terminal["proxyViolations"]:
            terminal.update(status="failed_consumed", reason="proxy_violation")
        ledger.close()
        write_once(directory / "result.json", terminal)
    return terminal


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    spec = prepare_spec(shared._git("rev-parse", "HEAD"))
    if args.mode == "prepare":
        DIRECTORY.mkdir(exist_ok=False)
        write_once(DIRECTORY / "manifest.json", spec)
        print("prepared " + sha256((DIRECTORY / "manifest.json").read_bytes()).hexdigest())
    else:
        raw = (DIRECTORY / "manifest.json").read_bytes()
        require(sha256(raw).hexdigest() == args.manifest_sha256 and decode(raw) == spec, "manifest_drift")
        require(not any((DIRECTORY / name).exists() for name in ("consumed.json", "result.json", "journal.jsonl")),
                "run_already_attempted")
        result = run(spec, DIRECTORY)
        print(canonical({key: result[key] for key in ("status", "reason", "counts", "cleanup")}).decode())
        raise SystemExit(0 if result["status"] == "completed" and result["cleanup"] else 1)


if __name__ == "__main__":
    main()
