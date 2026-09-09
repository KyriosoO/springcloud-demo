"""One authorized Rewrite8 request, finite exception sites, no retrieval or raw output."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.knowledge import evidence_requirements as requirements
from agent_runtime.knowledge import rewrite_v7
from agent_runtime.knowledge.errors import KnowledgeInputError
from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v8 import KnowledgeRewriteTaskV8
from agent_runtime.model import gateway
from agent_runtime.model.contracts import InvalidModelOutput, ModelCallContext, QuestionEgressDisposition
from agent_runtime.model.deepseek.dto import project_deepseek_request
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings
from tests.system_e2e.knowledge_model_failure_probe_v1 import project_failure
from tests.system_e2e.knowledge_stage_b_cases import CASES

REPO = Path(__file__).resolve().parents[3]
RUN_ID = "knowledge-rewrite-diagnostic-v1-20260909-01"
ROOT = REPO / "agent-runtime" / "target" / RUN_ID
REFERENCE = "UAT_01:14.34"
LIMITS = dict(model=1, e2e=0, selection=0, summary=0, search=0, embedding=0, rerank=0,
              business=0, answer=0, retry=0, resume=0)

# Static source locations are valid only with the frozen code hashes checked before execution.
# Frames supply identity and line number ONLY: never locals, globals, messages or arbitrary paths.
SITES = {
    rewrite_v7._parse.__code__: {
        114: "task_response", 116: "task_json", 120: "root_fields", 124: "field_types",
        127: "list_limits", 131: "query_fields", 136: "requirement_fields",
        139: "requirement_kind", 143: "question_kind",
    },
    rewrite_v7._unique.__code__: {103: "duplicate_key"},
    rewrite_v7._constant.__code__: {109: "non_finite"},
    rewrite_v7.validate_requirement_plan_output.__code__: {
        68: "plan_types", 75: "query_contract", 82: "terminal_payload", 85: "missing_conditions",
        87: "unsupported_conditions", 89: "outcome",
    },
    requirements.validate_evidence_requirements.__code__: {
        48: "requirement_header", 57: "requirement_item", 59: "domain_coverage", 66: "applicability_roles",
    },
}


def throw_site(error):
    result = "unknown"
    for _ in range(8):
        if type(error) not in (InvalidModelOutput, KnowledgeInputError, ValueError, TypeError, json.JSONDecodeError):
            break
        trace = error.__traceback__
        for _ in range(32):
            if trace is None:
                break
            result = SITES.get(trace.tb_frame.f_code, {}).get(trace.tb_lineno, result)
            trace = trace.tb_next
        error = error.__cause__
    return result


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(("git", *args), cwd=REPO).decode("utf-8").strip()


def task_input():
    decision = QuestionEgressGuard().evaluate(CASES[1]["question"])
    if decision.disposition is not QuestionEgressDisposition.ALLOWED:
        raise ValueError("diagnostic.input_denied")
    return KnowledgeSemanticPlanInput(minimized_question=decision.minimized_question,
                                      enabled_domain_ids=("tax.policy", "tax.law"))


def manifest():
    if git("status", "--porcelain"):
        raise ValueError("diagnostic.dirty_worktree")
    source = (REPO / "agent-runtime/src").resolve()
    for name, module in tuple(sys.modules.items()):
        if name == "agent_runtime" or name.startswith("agent_runtime."):
            location = getattr(module, "__file__", None)
            if location is None or not Path(location).resolve().is_relative_to(source):
                raise ValueError("diagnostic.import_source_invalid")
    paths = git("ls-files", "agent-runtime/src", "agent-runtime/tests/system_e2e/knowledge*",
                "agent-runtime/tests/system_e2e/test_knowledge_rewrite_diagnostic_v1.py",
                "docs/plans/UAT_01_SINGLE_AGENT_KNOWLEDGE_ACCEPTANCE_TEST_PLAN.md").splitlines()
    request = KnowledgeRewriteTaskV8.definition().build_request(task_input())
    return dict(schemaVersion=1, runId=RUN_ID, authorizationReference=REFERENCE, frozenHead=git("rev-parse", "HEAD"),
                assets={name: digest((REPO / name).read_bytes()) for name in paths},
                taskVersion="8", model=ModelSettings.MODEL_NAME, limits=LIMITS,
                promptSha256=digest(request.system_instruction.encode()),
                requestSha256=digest(canonical_json_bytes(project_deepseek_request(request).payload)),
                caseId=CASES[1]["caseId"], sourceResultSha256="de416286b8ac6d416781f7e6f22b4cc57f6d84fa8dd5f03a25bb7fce6e3dd4b0")


def save(path, value):
    with path.open("xb") as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


async def measure(client, settings, root, binding):
    calls = 0
    diagnostics = []
    expected = canonical_json_bytes(project_deepseek_request(KnowledgeRewriteTaskV8.definition().build_request(task_input())).payload)

    async def outbound(request):
        nonlocal calls
        if calls or request.method != "POST" or str(request.url) != ModelSettings.BASE_URL + "/chat/completions" or request.content != expected:
            raise ValueError("diagnostic.outbound_forbidden")
        save(root / "consumed.json", dict(runId=RUN_ID, manifestSha256=binding, modelAttempts=1))
        save(root / "journal.jsonl", dict(ordinal=1, taskId="knowledge_rewrite", taskVersion="8"))
        calls += 1

    client.event_hooks["request"] = [outbound]
    original = gateway.model_call_failed

    def failed(sequence, kind):
        if kind == "invalid_output":
            error = sys.exception()
            diagnostics.append({**asdict(project_failure(error)), "throwSite": throw_site(error)})
        original(sequence, kind)

    try:
        definition = KnowledgeRewriteTaskV8.definition()
        model = gateway.BoundedStructuredModelGateway(
            transport=DeepSeekChatTransport(settings=settings, client=client), definitions=(definition,), max_concurrency=1)
        with patch.object(gateway, "model_call_failed", failed):
            result = await model.generate(definition=definition, input=task_input(), context=ModelCallContext(
                request_id=RUN_ID, correlation_id=RUN_ID, deadline_monotonic=asyncio.get_running_loop().time() + 10))
        summary = dict(outcome=result.output.outcome, queryCount=len(result.output.queries),
                       requirementCount=len(result.output.evidence_requirements)) if result.output is not None else None
        value = dict(status="measured", failureKind=result.failure_kind.value if result.failure_kind else None,
                     outputSummary=summary, diagnostics=diagnostics)
    except BaseException as error:
        value = dict(status="interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "runner_failed",
                     failureKind="execution_failed", outputSummary=None, diagnostics=diagnostics)
    finally:
        await client.aclose()
    value.update(schemaVersion=1, runId=RUN_ID, manifestSha256=binding, counts={**{k: 0 for k in LIMITS}, "model": calls},
                 clientClosed=client.is_closed)
    save(root / "result.json", value)
    return value


async def execute(expected_sha):
    if {p.name for p in ROOT.iterdir()} != {"manifest.json"}:
        raise ValueError("diagnostic.retry_resume_forbidden")
    raw = (ROOT / "manifest.json").read_bytes()
    if digest(raw) != expected_sha or json.loads(raw) != manifest():
        raise ValueError("diagnostic.binding_changed")
    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey(os.environ.get("LLM_API_KEY", "")))
    return await measure(build_deepseek_http_client(settings), settings, ROOT, expected_sha)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("prepare", "execute"))
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)
    try:
        if args.operation == "prepare":
            value = manifest()
            ROOT.mkdir(parents=True, exist_ok=False)
            save(ROOT / "manifest.json", value)
            print(json.dumps(dict(runId=RUN_ID, frozenHead=value["frozenHead"], manifestSha256=digest((ROOT / "manifest.json").read_bytes()))))
        else:
            if not args.manifest_sha256:
                raise ValueError("diagnostic.binding_required")
            print(json.dumps(asyncio.run(execute(args.manifest_sha256)), sort_keys=True))
    except Exception:
        raise SystemExit("diagnostic.preflight_or_persistence_failed") from None


if __name__ == "__main__":
    main()
