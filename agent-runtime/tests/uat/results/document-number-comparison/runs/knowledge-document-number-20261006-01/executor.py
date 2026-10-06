"""One human-authorized document-number comparison; no retry or paid model."""
import asyncio
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import os
import sys
import time

ROOT = Path("D:/codex")
sys.path[:0] = [str(ROOT / "agent-runtime"), str(ROOT / "agent-runtime/src"),
                str(ROOT / "knowledge-corpus-tools/src")]
import httpx
from agent_runtime.api.cancellation import MutableCancellationSignal
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_projection import projected_java_pair
from tests.evaluation.knowledge.rebuild_document_number_identity import (
    IdentityCapture, ModelBinding, capture_static_identity,
)
from tests.evaluation.knowledge.rebuild_document_number_inventory import InventoryCapture
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_proxy import metadata_paths
from tests.evaluation.knowledge.rebuild_document_number_runner import (
    ConfirmationReceipt, IndependentRunner, RunScope,
)
from tests.evaluation.knowledge.rebuild_b_local_runner import _bounded_model_process
from knowledge_corpus_tools import b_model_identity_v1 as models

HEAD = "89bf287738c64e28645cbfb8e199f96d63f242c9"
RUN = "knowledge-document-number-20261006-01"
REFERENCE = "P3_01:14.57-execution"
BASE = ROOT / "agent-runtime/tests/uat/results/document-number-comparison"
PREP = BASE / "runs/knowledge-document-number-20261004-01"
HERE = Path(__file__).resolve().parent
PORTS = (19211, 19212, 19311, 19312)
DOCKER_SHA = "f71e5a9fe6a8db10c7296ad6fdf0c1d7d79634e644d7ec1e8a2c18d7dcb52d21"


def write_once(path, raw):
    with path.open("xb") as stream:
        p.require(stream.write(raw) == len(raw), "executor_short_write")
        stream.flush()
        os.fsync(stream.fileno())


def checked(path, digest):
    raw = path.read_bytes()
    p.require(sha256(raw).hexdigest() == digest, "executor_preparation_asset_drift")
    return raw


def main():
    p.require(p._git(ROOT, "rev-parse", "HEAD").decode().strip() == HEAD
        and p._git(ROOT, "branch", "--show-current").decode().strip() == "codex_0915"
        and not p._git(ROOT, "status", "--porcelain=v1", "--untracked-files=no").strip(),
        "executor_repository_drift")
    models._require_locked_corpus_environment()
    marker = BASE / "consumed" / (RUN + ".json")
    directory = BASE / "runs" / RUN
    p.require(not marker.exists() and not directory.exists(), "executor_reuse_forbidden")
    old_identity = json.loads(checked(PREP / "identity.json",
        "82393a6cc1cb2e663a1fb3d0bf67eaaa1dfcdea6f56e3b4d49acce86240dcb12"))
    old_captures = json.loads(checked(PREP / "captures.json",
        "f58eb1c0acb8f88067b53df91bf26cba9d8a37ba8e0ce998413e1621c3f96218"))
    inventory_raw = checked(PREP / "inventory.json",
        "e2178b1ee9f13ce840e1a1b878cc7778e554ab1319eecb7e73b0ed1baa5a6f96")
    binding = ReadBinding(**old_identity["static"]["binding"])
    prior = old_captures["inventory"]
    inventory = InventoryCapture(binding, prior["mappingSha256"], prior["recordCount"],
        prior["sourceFingerprint"], prior["inventorySha256"],
        tuple((path, prior["metadataSha256"][path]) for path in metadata_paths(binding)), inventory_raw)
    old = json.loads((ROOT / "knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json").read_bytes())
    model = ModelBinding(old_identity["models"]["embedding"]["container"]["id"],
        old_identity["models"]["rerank"]["container"]["id"],
        sha256(models._canonical(old["modelSnapshot"]["model"])).hexdigest(),
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        DOCKER_SHA, old_identity["docker"]["host"])
    model.verify_executable()
    print("offline_build_started", flush=True)
    outcome = None
    reason = "completed"
    with projected_java_pair() as pair:
        p.require(pair.draft.frozen_head == HEAD, "executor_projection_drift")
        static = capture_static_identity(pair, binding)
        # This is an EXPECTED composite, not a new observed model capture.
        # The runner must prove exact equality with actual pre/post probes.
        expected_material = p.canonical({"static": p._decode(static),
            "models": old_identity["models"], "docker": {"host": model.docker_host,
                "executableSha256": model.docker_sha256}})
        expected_identity = IdentityCapture(sha256(static).hexdigest(),
            old_identity["models"]["sha256"], sha256(expected_material).hexdigest(), expected_material)
        now = int(time.time())
        scope = RunScope(RUN, REFERENCE, "execution", "live_attempts", now, now + 3600,
            pair, binding, model, inventory.mapping_sha256, sha256(static).hexdigest(),
            inventory.record_count, PORTS, inventory, expected_identity)
        p.require(sum(dict(scope.limits()).values()) == 269, "executor_budget_mismatch")
        authorization = scope.material()
        decision = p.canonical({"kind": "human_decision_record_v1", "humanReply": "确认，继续目标",
            "acceptedProposal": "independent document-number comparison: HTTP<=269, identity<=8;"
                "no paid LLM, no index/alias writes; exclusive target-index/alias window",
            "runId": RUN, "reference": REFERENCE, "sourceHead": HEAD,
            "authorizationSha256": sha256(authorization).hexdigest(),
            "executorSha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "exclusiveWindowConfirmed": True, "window": {"notBefore": now, "expiresAt": now + 3600},
            "previousPreparationUsedAsExpectedBaselineOnly": True,
            "dockerLocalPreflight": {"previousSha256": old_identity["docker"]["executableSha256"],
                "currentSha256": DOCKER_SHA, "signatureStatus": "Valid", "publisher": "Docker Inc",
                "fileVersion": "29.8.2", "initialRestrictedAttempts": 0,
                "initialScopeConsumed": False}})
        # Durable scope/decision before consumption and any restricted operation.
        write_once(HERE / "authorization.json", authorization)
        write_once(HERE / "decision.json", decision)
        write_once(HERE / "projection.json", p.canonical(pair.report))
        write_once(HERE / "expected-identity.json", expected_material)
        write_once(HERE / "expected-inventory.json", p.canonical(inventory.preview()))

        def confirm(raw):
            p.require(raw == authorization, "executor_confirmation_drift")
            return ConfirmationReceipt(sha256(raw).hexdigest(), REFERENCE, sha256(decision).hexdigest())

        def client():
            return httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                follow_redirects=False, timeout=httpx.Timeout(30), transport=httpx.HTTPTransport(retries=0))

        runner = IndependentRunner(scope=scope, authorization=authorization, confirm=confirm,
            process=lambda command, raw: _bounded_model_process(command, payload=raw, timeout=300), client=client)
        print("independent_scope_frozen_no_paid_llm", flush=True)
        try:
            outcome = asyncio.run(runner.evaluate(cancellation=MutableCancellationSignal()))
        except (Exception, KeyboardInterrupt) as error:
            reason = str(error) if type(error) is p.ProtocolError else "executor_failed"
        if outcome is not None:
            p.require(outcome.comparison is not None, "executor_comparison_missing")
            write_once(HERE / "comparison.json", p.canonical(asdict(outcome.comparison)))
            write_once(HERE / "observed-identity.json", outcome.identity.material)
            write_once(HERE / "observed-inventory.json", p.canonical(outcome.inventory.preview()))
        released = pair.resources_released
    # This line is reached only after the actual offline build lease closed.
    journal_rows = [] if not directory.exists() else [json.loads(row) for row in
        (directory / "attempts.jsonl").read_bytes().splitlines()]
    closure = next((row for row in reversed(journal_rows) if row.get("event") == "journal_closed"), None)
    result = {"kind": "document_number_execution_result_v1", "runId": RUN, "frozenHead": HEAD,
        "status": "completed" if outcome is not None else "failed_consumed" if marker.exists() else "failed_unconsumed",
        "reason": reason, "httpCounts": None if closure is None else closure["counts"],
        "modelIdentityCounts": None if closure is None else closure["nonHttpModelIdentityCounts"],
        "journalSealed": closure is not None,
        "reportedCleanup": None if closure is None else closure["reportedCleanup"],
        "offlineBuildLeaseReleased": released, "caseCount": 0 if outcome is None else len(outcome.comparison.stage.cases),
        "qualityAssessment": "Not assessed", "releaseAllowed": False,
        "paidModel": 0, "business": 0, "indexAliasWrites": 0, "retry": 0, "resume": 0}
    write_once(HERE / "result.json", p.canonical(result))
    if directory.exists():
        for source in HERE.iterdir():
            if source.is_file() and source.suffix in (".json", ".py"):
                write_once(directory / source.name, source.read_bytes())
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return 0 if outcome is not None else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("executor_terminal_failure_no_retry", flush=True)
        sys.exit(3)
