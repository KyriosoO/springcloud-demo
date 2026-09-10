"""UAT_01 14.48: one paid Summary7, fixed planning, real authorized local reads.

Not a full-model UAT. No production hook, raw response, question or body output.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
from unittest.mock import patch

from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge.evidence.requirement_validation import RequirementCoverageValidator
from agent_runtime.knowledge.evidence.summary_task_v7 import SUMMARY_PROMPT_V7
from agent_runtime.knowledge.evidence.summary_validation import ExtractiveSummaryValidator, InvalidSummary
from agent_runtime.model.contracts import ModelTaskId
from agent_runtime.model.deepseek.dto import project_deepseek_request
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.evaluation.knowledge.retrieval_benchmark_dataset import load_dataset
from tests.system_e2e import knowledge_activation_local_smoke as smoke
from tests.system_e2e.knowledge_summary_failure_probe_v1 import project_summary_failure

REPO = Path(__file__).resolve().parents[3]
RUN_ID = "knowledge-summary-diagnostic-v1-20260910-01"
ROOT = REPO / "agent-runtime/target" / RUN_ID
REFERENCE = "UAT_01:14.48"
CASE_ID = "KRB-001"
LOCAL_LIMITS = {"search": 2, "embedding": 1, "rerank": 2}
LIMITS = {**LOCAL_LIMITS, "model": 1, "warmup": 1, "partialModelRuntime": 1,
          "selectionPaid": 0, "rewritePaid": 0, "business": 0, "answer": 0, "retry": 0, "resume": 0}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(("git", *args), cwd=REPO).decode("utf-8").strip()


def save(path, value):
    with path.open("xb") as stream:
        stream.write(canonical_json_bytes(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def artifacts():
    values = smoke.support_source.artifact_hashes()
    for path in sorted((REPO / "es-query-service/target/classes").rglob("*")):
        if path.is_file():
            values[path.relative_to(REPO).as_posix()] = digest(path.read_bytes())
    return values


def manifest():
    smoke.require(not git("status", "--porcelain"), "dirty_worktree")
    source = (REPO / "agent-runtime/src").resolve()
    for name, module in tuple(sys.modules.items()):
        if name == "agent_runtime" or name.startswith("agent_runtime."):
            location = getattr(module, "__file__", None)
            smoke.require(location is not None and Path(location).resolve().is_relative_to(source), "import_source_invalid")
    paths = git("ls-files", "agent-runtime/src", "agent-runtime/tests/system_e2e/knowledge*",
        "agent-runtime/tests/system_e2e/test_knowledge_summary_diagnostic_v1.py",
        "agent-runtime/tests/evaluation/knowledge/retrieval_benchmark*", "agent-runtime/tests/helpers.py",
        "serviceCenter/knowledge-runtime-binding.v2.json", "serviceCenter/warmup-knowledge-reranker.py",
        "knowledge-corpus-tools/scripts/validate-policy-vector-typed-v1.py",
        "docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md").splitlines()
    return {"schemaVersion": 1, "runId": RUN_ID, "authorizationReference": REFERENCE,
        "frozenHead": git("rev-parse", "HEAD"), "caseId": CASE_ID, "limits": LIMITS,
        "assets": {p: digest((REPO / p).read_bytes()) for p in paths},
        "artifacts": artifacts(), "datasetSha256": load_dataset().sha256,
        "taskVersion": "7", "model": ModelSettings.MODEL_NAME,
        "promptSha256": digest(SUMMARY_PROMPT_V7.encode()), "knownPaidBefore": 54}


@contextmanager
def validation_observer(record):
    """One sequential request; wrappers never change inputs, output or errors."""
    def wrap(original, phase):
        def validate(self, **kwargs):
            record["phases"].append(phase)
            try:
                return original(self, **kwargs)
            except InvalidSummary as error:
                record["failures"].append(asdict(project_summary_failure(error)))
                raise
        return validate

    with patch.object(RequirementCoverageValidator, "validate", wrap(RequirementCoverageValidator.validate, "coverage")), \
            patch.object(ExtractiveSummaryValidator, "validate", wrap(ExtractiveSummaryValidator.validate, "extractive")):
        yield


class OneSummary(smoke.FixedModel):
    def __init__(self, case, root, binding, *, client_factory=build_deepseek_http_client, settings_factory=None):
        super().__init__(case)
        self.root, self.binding = root, binding
        self.client_factory = client_factory
        self.settings_factory = settings_factory or (lambda: ModelSettings(provider=ModelProvider.DEEPSEEK,
            api_key=ModelApiKey(os.environ.get("LLM_API_KEY", ""))))
        self.client = None
        self.paid = 0
        self.expected = None

    async def outbound(self, request):
        smoke.require(not self.paid and request.method == "POST"
            and str(request.url) == ModelSettings.BASE_URL + "/chat/completions"
            and request.content == self.expected, "model_outbound_forbidden")
        save(self.root / "consumed.json", {"runId": RUN_ID, "manifestSha256": self.binding, "modelAttempts": 1})
        save(self.root / "journal.jsonl", {"ordinal": 1, "taskId": "knowledge_summary", "taskVersion": "7"})
        self.paid += 1

    async def complete(self, request, *, call_deadline):
        if request.task_id is not ModelTaskId.KNOWLEDGE_SUMMARY:
            return await super().complete(request, call_deadline=call_deadline)
        # Parent enforces order/version and records hashes, but its fake answer
        # is discarded. Only the actual transport response reaches the gateway.
        await super().complete(request, call_deadline=call_deadline)
        coverage = json.loads(request.user_payload_json)["coverage"]
        smoke.require(coverage["retrieval_complete"] is True and coverage["domain_coverage_complete"] is True,
                      "partial_retrieval_not_measured")
        self.expected = canonical_json_bytes(project_deepseek_request(request).payload)
        save(self.root / "summary_prepared.json", {"requestSha256": digest(self.expected),
            "evidenceHashes": self.evidence_hashes, "taskId": "knowledge_summary", "taskVersion": "7"})
        settings = self.settings_factory()  # First and only credential read, after authorized projection.
        self.client = self.client_factory(settings)
        self.client.event_hooks["request"] = [self.outbound]
        return await DeepSeekChatTransport(settings=settings, client=self.client).complete(request, call_deadline=call_deadline)

    async def close(self):
        if self.client is not None:
            await self.client.aclose()


async def measure(case, token, root, binding, budget, *, model_factory=OneSummary):
    model = model_factory(case, root, binding)
    diagnostics = {"phases": [], "failures": []}
    states = []
    original_scope = smoke.observation_scope

    @contextmanager
    def observe():
        with original_scope() as collector:
            try:
                yield collector
            finally:
                states.extend({k: entry[k] for k in ("taskId", "taskVersion", "status", "failureKind")}
                              for entry in collector.snapshot().model_calls)

    try:
        with patch.object(smoke, "FixedModel", lambda unused: model), patch.object(smoke, "observation_scope", observe), \
                validation_observer(diagnostics):
            _, row = await smoke.run_case(case, token, budget)
        # The inherited list names all transport calls; split fake/real honestly.
        row.pop("fakeModelTasks")
        row["modelTaskStates"] = states
        row["validation"] = diagnostics
        row["externalModelCalls"] = model.paid
        row["fixedPlanningCalls"] = len(model.calls) - int("knowledge_summary" in model.calls)
        return row
    finally:
        await model.close()


def execute(expected_sha):
    smoke.require({p.name for p in ROOT.iterdir()} == {"manifest.json"}, "retry_resume_forbidden")
    raw = (ROOT / "manifest.json").read_bytes()
    frozen = json.loads(raw)
    smoke.require(digest(raw) == expected_sha and frozen == manifest(), "binding_changed")
    save(ROOT / "started.json", {"runId": RUN_ID, "manifestSha256": expected_sha})
    terminal = {"schemaVersion": 1, "runId": RUN_ID, "manifestSha256": expected_sha, "status": "failed",
        "warmupCalls": 0, "partialModelRuntime": 0, "business": 0, "answer": 0, "retry": 0, "resume": 0,
        "indexWrites": 0, "case": None, "limitations": ["fixed_planning", "not_full_model_uat", "no_spring_http_hop"]}
    budget = smoke.LocalBudget()
    try:
        support = smoke.support_source.load_support()
        dataset = load_dataset()
        binding = json.loads(support.checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v2.json", dataset.binding_sha256))
        smoke.require((REPO / "es-query-service/src/main/resources/application-knowledge-live.yml").read_bytes()
            == (REPO / "es-query-service/target/classes/application-knowledge-live.yml").read_bytes(), "compiled_profile_stale")
        for port in support.PORTS:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", port))
        support.java_executable()
        smoke.support_source.check_index(support, binding)
        terminal["warmupCalls"] = 1
        asyncio.run(runpy.run_path(str(REPO / "serviceCenter/warmup-knowledge-reranker.py"))["warmup"]())
        with support.isolated_services(binding, binding["readAlias"], terminal) as tokens, patch.object(smoke, "LIMITS", LOCAL_LIMITS):
            terminal["partialModelRuntime"] = 1
            terminal["case"] = asyncio.run(measure(next(c for c in dataset.cases if c.id == CASE_ID), tokens["admin"], ROOT, expected_sha, budget))
        smoke.support_source.check_index(support, binding)
        smoke.require(artifacts() == frozen["artifacts"], "artifacts_changed")
        row = terminal["case"]
        smoke.require(row["externalModelCalls"] == 1 and row["retrievalPathsComplete"] and not budget.stopped, "measurement_incomplete")
        terminal["status"] = "measured"
    except BaseException as error:
        terminal["failureReason"] = "interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "execution_failed"
    finally:
        terminal["counts"] = {key: budget.counts[key] for key in LOCAL_LIMITS}
        # Consumed marker conservatively counts attempted outbound even if the
        # runner is interrupted after persistence but before a network response.
        terminal["modelAttempts"] = int((ROOT / "consumed.json").exists())
        save(ROOT / "result.json", terminal)
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        if args.operation == "prepare":
            value = manifest()
            ROOT.mkdir(parents=True, exist_ok=False)
            save(ROOT / "manifest.json", value)
            print(json.dumps({"runId": RUN_ID, "frozenHead": value["frozenHead"],
                              "manifestSha256": digest((ROOT / "manifest.json").read_bytes())}))
        else:
            smoke.require(bool(args.manifest_sha256), "binding_required")
            result = execute(args.manifest_sha256)
            print(json.dumps({k: result[k] for k in ("runId", "status", "modelAttempts", "counts")}, sort_keys=True))
            return 0 if result["status"] == "measured" else 1
    except Exception:
        raise SystemExit("summary_diagnostic.preflight_or_persistence_failed") from None


if __name__ == "__main__":
    raise SystemExit(main())
