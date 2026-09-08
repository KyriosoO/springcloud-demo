"""One authorized current-production run; no mutation or replay of frozen runners."""
from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
import importlib
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

from agent_runtime.knowledge.retrieval.bge_rerank_context import ContextualBgeRerankAdapter
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from tests.system_e2e import knowledge_stage_b_services as services
from tests.system_e2e import knowledge_stage_b_quality_v3_probe as probe
from tests.system_e2e import knowledge_stage_b_uat_v8 as previous

legacy = previous.legacy
CASES, GOLD = previous.CASES, previous.GOLD
same_json, strict_json = previous.same_json, previous.strict_json
RUN_ID = "knowledge-stage-b-uat-v9-20260908-run-09"
REFERENCE = "P3_00:WP-KRETRIEVAL-UAT-01/run-09"
LIMITS = dict(e2e=10, model=28, search=32, embedding=16, rerank=32, business=0, retry=0, resume=0)
TOTAL_LIMITS = dict(e2e=26, model=67, search=80, embedding=40, rerank=52, business=0, retry=0, resume=0)
STARTUP_LIMITS = dict(rerank=1)
TASKS = {**previous.TASKS, "knowledge_rewrite": "8"}
INSTRUCTION = KnowledgeRewriteTaskV8.definition().build_request(KnowledgeSemanticPlanInput(
    minimized_question="税务政策定义", enabled_domain_ids=("tax.policy", "tax.law"))).system_instruction
BINDING = "serviceCenter/knowledge-runtime-binding.v2.json"
WARMUP = "serviceCenter/warmup-knowledge-reranker.py"
_manifest = previous.current_manifest
_validate_authorized = previous.validate_authorized
_authorization = previous.authorization
_run_server = previous.run_server
_checked_services = previous.checked_services
_budget = previous.Run08Budget
_active_manifest = None


def prior_bindings():
    rows = []
    for ordinal in range(1, 9):
        history = importlib.import_module(f"tests.system_e2e.test_knowledge_stage_b_run_{ordinal:02}_history")
        root = Path(__file__).with_name(f"knowledge_stage_b_run_{ordinal:02}")
        if any(legacy.digest((root / name).read_bytes()) != sha for name, sha in history.HASHES.items()):
            raise ValueError("stage_b.prior_run_changed")
        value = strict_json((root / "result.json").read_bytes())
        if value["status"] != "failed" or set(value["totals"]) != set(LIMITS):
            raise ValueError("stage_b.prior_status_invalid")
        rows.append(dict(runId=value["runId"], hashes=history.HASHES, calls=value["totals"]))
    for key, maximum in TOTAL_LIMITS.items():
        counts = [row["calls"][key] for row in rows]
        if (any(type(c) is not int or c < 0 for c in counts)
                or sum(counts) + LIMITS[key] + STARTUP_LIMITS.get(key, 0) > maximum):
            raise ValueError("stage_b.cumulative_budget_invalid")
    return rows


def current_manifest(root):
    value = _manifest(root)
    extras = (BINDING, WARMUP, str(probe.HELPER.relative_to(legacy.REPO)).replace("\\", "/"))
    for name in extras:
        value["assets"][name] = legacy.digest((legacy.REPO / name).read_bytes())
    value.update(schemaVersion=9, taskVersions=dict(selection=TASKS["action_selection"], rewrite="8", summary="6"),
                 indexBinding=strict_json((legacy.REPO / BINDING).read_text(encoding="utf-8-sig")),
                 rerankInputVersion=ContextualBgeRerankAdapter.INPUT_VERSION,
                 startupLimits=STARTUP_LIMITS, localModels=probe.local_models())
    return value


def validate_manifest(root, expected_sha=None):
    allowed = {"manifest.json", "authorization.json", "environment.jsonl", "startup.jsonl"}
    if any(p.name not in allowed or not p.is_file() for p in root.iterdir()):
        raise ValueError("stage_b.retry_resume_forbidden")
    raw = (root / "manifest.json").read_bytes()
    sha = legacy.digest(raw)
    if expected_sha is not None and sha != expected_sha:
        raise ValueError("stage_b.manifest_sha_mismatch")
    value = strict_json(raw)
    if not same_json(value, current_manifest(root)):
        raise ValueError("stage_b.run_09_binding_invalid")
    return value, sha


def validate_startup(root, sha):
    rows = [strict_json(line) for line in (root / "startup.jsonl").read_bytes().splitlines()]
    expected = [dict(stage="warmup_attempt", runId=RUN_ID, manifestSha256=sha, rerank=1, model=0),
                dict(stage="warmup_ready", rerank=1, items=40, clientsClosed=True)]
    if not same_json(rows, expected):
        raise ValueError("stage_b.startup_invalid")


def authorization(manifest, sha):
    root = Path(manifest["runRoot"])
    validate_startup(root, sha)
    validate_environment(root)
    return {**_authorization(manifest, sha), "startupLimits": STARTUP_LIMITS,
            "startupSha256": legacy.digest((root / "startup.jsonl").read_bytes()),
            "environmentSha256": legacy.digest((root / "environment.jsonl").read_bytes())}


def validate_environment(root):
    rows = [strict_json(line) for line in (root / "environment.jsonl").read_bytes().splitlines()]
    required = [dict(stage="local_model_readiness", embedding=True, rerank=True, model=0),
                dict(stage="spring_auth_stub_smoke", status="unsupported", model=0, knowledge=0),
                dict(stage="runtime_cleanup", clientsClosed=True),
                dict(stage="cleanup", ownedProcessesStopped=True, rawLogsDeleted=True, secretScanPassed=True),
                dict(stage="final_binding", unchanged=True)]
    if any(row.get("stage") == "failure" for row in rows) or not all(
            sum(same_json(row, wanted) for row in rows) == 1 for wanted in required):
        raise ValueError("stage_b.environment_preflight_invalid")


def validate_authorized(root, expected_sha):
    value, sha = _validate_authorized(root, expected_sha)
    validate_startup(root, sha)
    return value, sha


class CurrentServiceRoot:
    """Redirect only the historical test helper's fixed binding, not production IO."""

    def __truediv__(self, name):
        return legacy.REPO / (BINDING if name == "serviceCenter/knowledge-runtime-binding.v1.json" else name)


class Run09Budget(_budget):
    def count(self, kind):
        if self.current and self.current["reason"] and (
                kind != "model" or self.per_case["model"] >= 2):
            self.stopped = True
            raise ValueError("stage_b.clarification_outbound_rejected")
        return super().count(kind)


async def run_server(token, emit, budget=None):
    original = ContextualBgeRerankAdapter.rerank

    async def observe(adapter, **kwargs):
        scores = await original(adapter, **kwargs)
        if budget:
            ordered = sorted(scores, key=lambda item: (-item.score, item.candidate_index))
            budget.probes.append(dict(stage="rerank", inputVersion=ContextualBgeRerankAdapter.INPUT_VERSION,
                querySha256=legacy.digest(kwargs["query"].encode()), candidates=[
                    dict(chunkId=kwargs["candidates"][item.candidate_index].chunk_id,
                         sha256=kwargs["candidates"][item.candidate_index].content_sha256) for item in ordered]))
        return scores

    with patch.object(ContextualBgeRerankAdapter, "rerank", observe):
        return await _run_server(token, emit, budget)


def assert_environment():
    if _active_manifest is None:
        raise ValueError("stage_b.environment_binding_missing")
    if not same_json(probe.local_models(), _active_manifest["localModels"]):
        raise ValueError("stage_b.local_models_changed")
    probe.check_index(probe.load_support(), _active_manifest["indexBinding"])


@contextmanager
def checked_services(emit, *, include_agent=False):
    assert_environment()
    with patch.object(services, "REPO", CurrentServiceRoot()):
        with _checked_services(emit, include_agent=include_agent) as value:
            try:
                yield value
            finally:
                assert_environment()
                # Check code/executable set again; the runtime directory is excluded from assets.
                if not same_json(current_manifest(Path(_active_manifest["runRoot"])), _active_manifest):
                    raise ValueError("stage_b.post_run_binding_changed")
                emit(dict(stage="final_binding", unchanged=True))


async def _warmup():
    spec = importlib.util.spec_from_file_location("stage_b_run09_warmup", legacy.REPO / WARMUP)
    if spec is None or spec.loader is None:
        raise ValueError("stage_b.warmup_loader_invalid")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return await module.warmup()


async def warmup_once(root, sha):
    # The attempted operation is durable BEFORE the HTTP attempt, so crashes cannot cause a retry.
    with (root / "startup.jsonl").open("xb") as stream:
        probe.emit_line(stream, dict(stage="warmup_attempt", runId=RUN_ID, manifestSha256=sha, rerank=1, model=0))
        try:
            assert_environment()
            result = await _warmup()
            if (result.get("status") != "ready" or type(result.get("rerankCalls")) is not int
                    or result["rerankCalls"] != 1 or type(result.get("items")) is not int
                    or result["items"] != 40 or result.get("clientClosed") is not True):
                raise ValueError("stage_b.warmup_failed")
            probe.emit_line(stream, dict(stage="warmup_ready", rerank=1, items=40, clientsClosed=True))
        except (Exception, KeyboardInterrupt):
            probe.emit_line(stream, dict(stage="warmup_failed", reason="startup_failed"))
            raise SystemExit("stage_b.startup_failed") from None


@contextmanager
def bindings(manifest=None):
    with (patch.multiple(previous, RUN_ID=RUN_ID, REFERENCE=REFERENCE, LIMITS=LIMITS, TOTAL_LIMITS=TOTAL_LIMITS,
                         TASKS=TASKS, INSTRUCTION=INSTRUCTION, prior_bindings=prior_bindings,
                         current_manifest=current_manifest, validate_manifest=validate_manifest,
                         authorization=authorization, validate_authorized=validate_authorized,
                         Run08Budget=Run09Budget, run_server=run_server, checked_services=checked_services),
          patch.object(sys.modules[__name__], "_active_manifest", manifest), previous.run_08_bindings()):
        yield


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("prepare", "check-environment", "authorize", "execute"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    with bindings():
        if args.mode == "prepare":
            value = previous.prepare(args.root)
            print(json.dumps(dict(frozenHead=value["frozenHead"], manifestSha256=legacy.digest(
                (args.root / "manifest.json").read_bytes()), limits=LIMITS, startupLimits=STARTUP_LIMITS)))
            return
        if not args.manifest_sha256:
            raise ValueError("stage_b.manifest_sha_required")
        value, sha = validate_manifest(args.root, args.manifest_sha256)
        with patch.object(sys.modules[__name__], "_active_manifest", value):
            if args.mode == "check-environment":
                if {p.name for p in args.root.iterdir()} != {"manifest.json"}:
                    raise ValueError("stage_b.retry_resume_forbidden")
                asyncio.run(warmup_once(args.root, sha))
            elif args.mode == "authorize":
                # Check preflight before writing authorization, rather than relying on execute alone.
                proposed = authorization(value, sha)
                legacy.write_exclusive(args.root / "authorization.json", proposed)
                validate_authorized(args.root, sha)
                print(json.dumps(dict(runId=RUN_ID, manifestSha256=sha, authorized=True)))
                return
            with patch.object(sys, "argv", [sys.argv[0], args.mode, "--root", str(args.root), "--manifest-sha256", sha]):
                legacy.main()


if __name__ == "__main__":
    main()
