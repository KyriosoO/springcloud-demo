"""DR-KRET-035 / UAT_01 14.43: same-corpus, no-paid retrieval comparison.

Reuse the immutable baseline harness. Only the owned Java policy Profile gets
the opt-in flag; no online configuration, index, query fixture or gold changes.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import time
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from tests.system_e2e import knowledge_retrieval_benchmark_v1 as benchmark

base = benchmark.base
BASELINE = base.REPO / "agent-runtime/tests/evaluation/knowledge/retrieval_benchmark.result.v1.jsonl"
BASELINE_SHA = "1cc5f91c6ca5d7d9edb45354be17ca1c0b8a498b30c7e64cb3c78ff3febb521c"
BENCHMARK_SHA = "a817372f4cb0b3d7df8104bc8fd5f98ef4bec07bfea301e9df395152054daa11"
FLAG = "--es.query.knowledge.profiles.tax-policy-v1.document-number-matching=true"
MAIN_CLASS = "com.dylan.esquery.EsQueryServiceApplication"
EXTRA_CLASSES = (
    "service/DocumentNumberQuery.class", "service/DocumentNumberQuery$Reference.class",
    "config/KnowledgeSearchProperties.class", "config/KnowledgeSearchProperties$KnowledgeSearchProfile.class",
)
STABLE_ARTIFACTS = (
    "auth-service/target/auth-service-0.0.1-SNAPSHOT.jar",
    "es-query-service/target/stage-b-classpath.txt",
    "es-query-service/target/classes/application-knowledge-live.yml",
)


def load_baseline():
    raw = BASELINE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASELINE_SHA:
        raise ValueError("probe_artifacts_changed")
    if hashlib.sha256(Path(benchmark.__file__).read_bytes()).hexdigest() != BENCHMARK_SHA:
        raise ValueError("probe_support_changed")
    return json.loads(raw.splitlines()[0])


def validate_prepared(value, baseline):
    for key in ("bindingSha256", "catalogSha256", "fixtureSha256", "caseIds", "budgets",
                "localModelContainers", "datasetSha256", "rerankInputVersion"):
        if value[key] != baseline[key]:
            raise ValueError("probe_artifacts_changed")
    if any(value["artifactHashes"][p] != baseline["artifactHashes"][p] for p in STABLE_ARTIFACTS):
        raise ValueError("probe_artifacts_changed")


def configured_support(support, state):
    """Patch this dynamically loaded module, never the global subprocess module."""
    original = support.subprocess

    def launch(command, **kwargs):
        if (type(command) is not list or not all(type(x) is str for x in command)
                or any("document-number-matching" in x for x in command)):
            raise ValueError("probe_outbound_rejected")
        if MAIN_CLASS in command:
            if (Path(kwargs["cwd"]).resolve() != (base.REPO / "es-query-service").resolve()
                    or command.count(MAIN_CLASS) != 1 or "--server.port=19201" not in command
                    or state["profileFlagLaunches"] != 0):
                raise ValueError("probe_outbound_rejected")
            state["profileFlagLaunches"] += 1
            command = [*command, FLAG]
        return original.Popen(command, **kwargs)

    support.subprocess = SimpleNamespace(**{**vars(original), "Popen": launch})
    return support


def expensive_queries_allowed(value):
    if type(value) is not dict:
        return False
    setting = None
    for source in ("defaults", "persistent", "transient"):
        layer = value.get(source, {})
        if type(layer) is not dict or type(layer.get("search", {})) is not dict:
            return False
        setting = layer.get("search", {}).get("allow_expensive_queries", setting)
    return setting is True or type(setting) is str and setting == "true"


def main():
    baseline = load_baseline()
    originals = base.load_support, base.artifact_hashes, base.check_index, base.emit_line
    state = {"profileFlagLaunches": 0, "clusterSettingReads": 0}

    def artifacts():
        value = originals[1]()
        for relative in EXTRA_CLASSES:
            path = "es-query-service/target/classes/com/dylan/esquery/" + relative
            value[path] = hashlib.sha256((base.REPO / path).read_bytes()).hexdigest()
        return value

    def check(support, binding):
        if state["clusterSettingReads"] >= 2:
            raise ValueError("probe_outbound_rejected")
        state["clusterSettingReads"] += 1
        with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                          timeout=5, headers={"Accept-Encoding": "identity"}) as client:
            status, raw = support.bounded_request(client, "GET", "/_cluster/settings?include_defaults=true"
                "&flat_settings=false&filter_path=defaults.search.allow_expensive_queries,"
                "persistent.search.allow_expensive_queries,transient.search.allow_expensive_queries")
        if status != 200 or not expensive_queries_allowed(json.loads(
                raw, object_pairs_hook=base._unique, parse_constant=base._reject_constant)):
            raise ValueError("probe_index_changed")
        originals[2](support, binding)

    def emit(stream, value):
        if value["event"] == "prepared":
            validate_prepared(value, baseline)
            value = {**value, "comparisonVersion": "document-number-benchmark-v1",
                     "comparisonSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "baselineSha256": BASELINE_SHA, "profileOverride": FLAG,
                     "clusterSettingReadBudget": 2,
                     "acceptance": "all_required_sources_preserved_and_missing_reference_sources_recovered"}
        if value["event"] == "terminal":
            value.update(state)
            if value["status"] == "measured" and state != {"profileFlagLaunches": 1, "clusterSettingReads": 2}:
                # Preserve a terminal record and make the underlying runner exit nonzero.
                value.update(status="failed", failureKind="ValueError", failureReason="probe_artifacts_changed")
        originals[3](stream, value)

    class TimedSearch(base.ObservedSearch):
        async def search(self, **kwargs):
            started = time.monotonic()
            result = await super().search(**kwargs)
            self.rows[-1]["durationMs"] = round((time.monotonic() - started) * 1000)
            return result

    with ExitStack() as scope:
        scope.enter_context(patch.object(base, "load_support", lambda: configured_support(originals[0](), state)))
        scope.enter_context(patch.object(base, "artifact_hashes", artifacts))
        scope.enter_context(patch.object(base, "check_index", check))
        scope.enter_context(patch.object(base, "emit_line", emit))
        scope.enter_context(patch.object(base, "ObservedSearch", TimedSearch))
        return benchmark.main()


if __name__ == "__main__":
    raise SystemExit(main())
