"""DR-KRET-024/025: one bounded alias publication with fail-closed rollback."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import types

REPO = Path(__file__).resolve().parents[2]
REHEARSAL_SHA = "76b8456e510bb2228bfafbabf75f31251d982541719191ab5630b8ea554f227b"
REHEARSAL_DRIVER_SHA = "b19f24a8d46779094c7c4ed27f6a1f953869df1004c7ecf57c1ab806b12657cf"


def support_module():
    path = REPO / "knowledge-corpus-tools/scripts/rehearse-policy-vector-rollback-v1.py"
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != REHEARSAL_DRIVER_SHA:
        raise ValueError("rehearsal_driver_changed")
    module = types.ModuleType("publication_rehearsal_support")
    module.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module, module.load_support()


class Publication:
    """Single operator window, not a distributed CAS; never overwrite drift."""

    def __init__(self, support, source, candidate, client):
        self.support, self.source, self.candidate, self.client = support, source, candidate, client
        self.alias = source["readAlias"]
        self.reads = self.writes = 0
        self.attempted = False

    def request(self, method, path, body=None):
        if method == "GET":
            if self.reads >= 30:
                raise ValueError("publication_read_budget")
            self.reads += 1
        else:
            if method != "POST" or path != "/_aliases" or self.writes >= 2:
                raise ValueError("publication_write_budget")
            self.writes += 1
        status, raw = self.support.bounded_request(self.client, method, path, json=body)
        from knowledge_corpus_tools.vector_candidate import _unique_pairs, _reject_constant
        if status != 200:
            raise ValueError("publication_http_failed")
        value = json.loads(raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
        if type(value) is not dict:
            raise ValueError("publication_response_invalid")
        return value

    def alias_state(self, binding):
        return {binding["expectedIndexName"]: {"aliases": {self.alias: {}}}}

    def identities(self):
        for binding in (self.source, self.candidate):
            name = binding["expectedIndexName"]
            raw = self.request("GET", f"/{name}/_settings")
            settings = raw[name]["settings"]["index"]
            block = settings.get("blocks", {}).get("write")
            if (set(raw) != {name} or settings["uuid"] != binding["expectedIndexUuid"]
                    or not (block is True or type(block) is str and block == "true")):
                raise ValueError("publication_identity_changed")

    def guard(self, binding):
        self.identities()
        if self.request("GET", f"/_alias/{self.alias}") != self.alias_state(binding):
            raise ValueError("publication_owner_changed")

    def move(self, before, after):
        self.guard(before)
        target = after["expectedIndexName"]
        if self.request("GET", f"/{target}/_alias") != {target: {"aliases": {}}}:
            raise ValueError("publication_target_has_alias")
        self.attempted = True
        reply = self.request("POST", "/_aliases", {"actions": [
            {"remove": {"index": before["expectedIndexName"], "alias": self.alias, "must_exist": True}},
            {"add": {"index": target, "alias": self.alias}},
        ]})
        if (set(reply) != {"acknowledged", "errors"}
                or reply["acknowledged"] is not True or reply["errors"] is not False):
            raise ValueError("publication_ack_invalid")
        self.guard(after)

    def restore_if_owned(self):
        # A lost response is inspected, never retried. Foreign ownership is left untouched.
        raw = self.request("GET", f"/_alias/{self.alias}")
        if raw == self.alias_state(self.source):
            self.guard(self.source)
            return "not_switched"
        if raw != self.alias_state(self.candidate):
            raise ValueError("publication_owner_changed")
        self.move(self.candidate, self.source)
        return "rolled_back"


def check_prerequisites(rehearsal, support):
    candidate, source, raw_catalog = support.preflight()
    proof = support.checked_bytes(REPO / "knowledge-corpus-tools/evidence/policy-vector-publication-20260907-b2/rollback-rehearsal-20260908-02.jsonl", REHEARSAL_SHA)
    rows = [json.loads(line) for line in proof.splitlines()]
    if rows[-1]["status"] != "passed" or rows[-1]["phasesPassed"] != 3:
        raise ValueError("rollback_not_verified")
    for port in (8090, 8091, 8092, 9201):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    for path, digest in (("serviceCenter/knowledge-runtime-binding.v2.json", support.BINDING_SHA),
                         ("agent-runtime/src/agent_runtime/knowledge/evidence/egress-policy-catalog-v3.json", support.CATALOG_SHA)):
        support.checked_bytes(REPO / path, digest)
    from agent_runtime.knowledge.evidence.catalog import KnowledgeEgressPolicyCatalog
    if KnowledgeEgressPolicyCatalog.load_current_resource().snapshot.source_sha256 != support.CATALOG_SHA:
        raise ValueError("current_catalog_mismatch")
    if "Join-Path $PSScriptRoot 'knowledge-runtime-binding.v2.json'" not in (REPO / "serviceCenter/run-all-services.ps1").read_text(encoding="utf-8"):
        raise ValueError("current_binding_mismatch")
    artifacts = rehearsal.artifact_hashes()
    if artifacts != rows[0]["artifactHashes"]:
        raise ValueError("rehearsed_artifacts_changed")
    return candidate, source, raw_catalog, artifacts


def verify_current_records(support, source, candidate, result):
    """Recheck every record immediately before publishing; bodies remain in memory."""
    import httpx
    from knowledge_corpus_tools.vector_candidate import VectorCandidateSpec, TRACE_FIELDS, _Build, _fingerprint, _write_blocked
    directory = REPO / "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2"
    binding = json.loads(support.checked_bytes(directory / "binding.json", "26d9644b3c2b30511249b79c09399557ced6dfb6f11d526829e43c6e2296ee3f"))
    build = json.loads(support.checked_bytes(directory / "result.json", "71f08b8be07738ce2925b2931387ff9e5ec1c1b3840b7fbb6a0273a0664de518"))
    spec = VectorCandidateSpec(**binding["spec"])
    allowed_search = {f"/{spec.source_index}/_search", f"/{spec.candidate_index}/_search"}
    result["integrityReadHttp"] = 0
    def budget(request):
        if result["integrityReadHttp"] >= 140 or not (request.method == "GET" or request.method == "POST" and request.url.path in allowed_search):
            raise ValueError("integrity_read_budget")
        result["integrityReadHttp"] += 1
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                      timeout=30, event_hooks={"request": [budget]}) as client:
        check = _Build(spec, client)
        old, new = check.source(), check.definition(spec.candidate_index)
        expected_mapping = {**old["mappings"],
            "_meta": {**old["mappings"].get("_meta", {}), "mapping_version": candidate["mappingVersion"]},
            "properties": {**old["mappings"]["properties"], **{key: {"type": "keyword"} for key in TRACE_FIELDS}}}
        if (old["aliases"] != {source["readAlias"]: {}} or new["aliases"] != {}
                or new["settings"]["index"]["uuid"] != candidate["expectedIndexUuid"]
                or not _write_blocked(new["settings"]["index"])
                or new["mappings"] != expected_mapping
                or any(old["settings"]["index"].get(key) != new["settings"]["index"].get(key)
                       for key in ("number_of_shards", "number_of_replicas", "analysis"))):
            raise ValueError("integrity_identity_changed")
        # The frozen fingerprint includes every text/ACL/trace field and float32 vector.
        for name, expected in ((spec.source_index, spec.source_fingerprint),
                               (spec.candidate_index, build["result"]["candidate_fingerprint"])):
            if _fingerprint(check.scan(name)) != expected:
                raise ValueError("integrity_records_changed")
        if check.source() != old or check.definition(spec.candidate_index) != new:
            raise ValueError("integrity_definition_changed")
        result["sourceFingerprint"] = spec.source_fingerprint
        result["candidateFingerprint"] = build["result"]["candidate_fingerprint"]


def publish(rehearsal, support, stream, result):
    import httpx
    candidate, source, raw_catalog, artifacts = check_prerequisites(rehearsal, support)
    for args in (["diff", "--quiet"], ["diff", "--cached", "--quiet"]):
        subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True)
    verify_current_records(support, source, candidate, result)
    rehearsal.emit(stream, {"event": "prepared", "schemaVersion": 1,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "source": source, "candidate": candidate, "catalogSha256": support.CATALOG_SHA,
        "bindingSha256": support.BINDING_SHA, "rollbackEvidenceSha256": REHEARSAL_SHA,
        "launcherSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "artifactHashes": artifacts,
        "budgets": {"typedCalls": 16, "embeddingCalls": 2, "onlineAliasWrites": 2, "esManagementReads": 30,
                    "integrityReadHttp": 140, "modelCalls": 0}})
    with httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False, follow_redirects=False,
                      timeout=5, headers={"Accept-Encoding": "identity"}) as client:
        manager = Publication(support, source, candidate, client)
        try:
            manager.move(source, candidate)
            rehearsal.emit(stream, {"event": "alias_switched", "alias": source["readAlias"], "index": candidate["expectedIndexName"]})
            with support.isolated_services(candidate, source["readAlias"], result) as tokens:
                asyncio.run(support.typed_checks(candidate, raw_catalog, tokens, result))
            if (result["typedCalls"] != 16 or result["embeddingCalls"] != 2
                    or len(result["checks"]) != 16
                    or not all(result.get(key) is True for key in ("profileVerifierStartupPassed", "ownedProcessesStopped", "rawLogsDeleted", "secretScanPassed"))):
                raise ValueError("publication_smoke_failed")
            if rehearsal.artifact_hashes() != artifacts:
                raise ValueError("publication_artifact_changed")
            manager.guard(candidate)
            # Flush the success checkpoint while rollback is still available.
            rehearsal.emit(stream, {"event": "smoke_passed", "typedCalls": 16, "embeddingCalls": 2})
            result.update(status="published", startupBinding="knowledge-runtime-binding.v2.json")
        except BaseException:
            if manager.attempted:
                result["rollback"] = manager.restore_if_owned()
                result["rollbackStartupBinding"] = "knowledge-runtime-binding.v1.json"
            raise
        finally:
            result.update(esManagementReads=manager.reads, onlineAliasWrites=manager.writes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute or sys.flags.optimize:
        parser.error("explicit --execute and non-optimized Python required")
    with args.result.open("xb") as stream:
        result = {"event": "terminal", "schemaVersion": 1, "status": "failed", "typedCalls": 0, "embeddingCalls": 0,
            "modelCalls": 0, "businessCalls": 0, "rerankCalls": 0, "retry": 0, "resume": 0, "checks": [],
            "limitations": ["not_quality_v3_e2e", "not_real_summary", "not_stage_b_uat"]}
        rehearsal = None
        try:
            rehearsal, support = support_module()
            publish(rehearsal, support, stream, result)
        except Exception:
            result["reason"] = "publication_failed_no_retry"
        finally:
            if rehearsal is None:
                stream.write((json.dumps(result, sort_keys=True) + "\n").encode())
                stream.flush()
            else:
                rehearsal.emit(stream, result)
            print(json.dumps({key: result[key] for key in ("status", "typedCalls", "embeddingCalls", "modelCalls")}))
    return 0 if result["status"] == "published" else 1


if __name__ == "__main__":
    raise SystemExit(main())
