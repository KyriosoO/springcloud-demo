"""Freeze or execute one B representation candidate; no comparison or publication.

`freeze` performs local contract checks only. `execute --execute-once` may write
one isolated ES candidate and call the local BGE service; it never calls an LLM.
Neither command retries or resumes an attempted run.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Literal

import httpx

from knowledge_corpus_tools.b_candidate_freeze_v1 import (
    BFreezeError, GitState, execute_b_candidate_v1, freeze_b_candidate_v1,
    finalize_b_assessment_v2, prepare_b_mapping_scans_v1, scan_b_mapping_arm_v1,
)
from knowledge_corpus_tools.local_representation_preparation_v1 import (
    LocalRepresentationVectorPreparationV1,
)
from knowledge_corpus_tools.rechunk_candidate_v1 import CandidateSpec

ROOT = Path(__file__).resolve().parents[2]
EXECUTION_SOURCES = (
    "knowledge-corpus-tools/src",
    "knowledge-corpus-tools/scripts/run-b-representation-candidate-v1.py",
    "agent-runtime/tests/uat/knowledge_rebuild_measure.v1.json",
)


def _git_state() -> GitState:
    def read(*args: str) -> str:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True,
            text=True, encoding="utf-8", check=False,
        )
        if result.returncode != 0:
            raise BFreezeError("git_state_invalid")
        return result.stdout.strip()

    return GitState(
        branch=read("branch", "--show-current"),
        head=read("rev-parse", "HEAD"),
        # Untracked Python modules are executable input too.  Unrelated document
        # edits do not change this runner's frozen code and must not block it.
        tracked_clean=not read("status", "--porcelain", "--untracked-files=all",
                               "--", *EXECUTION_SOURCES),
    )


def _read(path: Path, maximum: int) -> bytes:
    try:
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
    except OSError:
        raise BFreezeError("input_invalid") from None
    if not raw or len(raw) > maximum:
        raise BFreezeError("input_invalid")
    return raw


class LimitedLocalTransport(httpx.HTTPTransport):
    """No proxy/retry/redirect and a second hard request ceiling."""

    def __init__(self, *, port: int, maximum: int) -> None:
        super().__init__(retries=0, trust_env=False)
        self.port = port
        self.maximum = maximum
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (request.url.scheme != "http" or request.url.host != "127.0.0.1"
                or request.url.port != self.port
                or (self.port == 8908 and (
                    request.method != "POST" or request.url.path != "/embed"))
                or self.calls >= self.maximum):
            raise BFreezeError("budget_invalid")
        self.calls += 1
        return super().handle_request(request)


class ReadOnlyMappingTransport(LimitedLocalTransport):
    def __init__(self, *, index_name: str, maximum: int) -> None:
        super().__init__(port=9200, maximum=maximum)
        self.index_name = index_name

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if (request.method, request.url.path) not in {
            ("GET", f"/{self.index_name}"),
            ("POST", f"/{self.index_name}/_search"),
        }:
            raise BFreezeError("budget_invalid")
        return super().handle_request(request)


def _scan(output: Path, arm: Literal["source", "candidate"]) -> dict[str, Any]:
    plan = json.loads(_read(output / "scan-plan.json", 2 * 1024 * 1024))
    if arm == "source":
        name = plan["sourceIndex"]
    else:
        result = json.loads(_read(output / "result.json", 2 * 1024 * 1024))
        name = result["candidateIndex"]
    transport = ReadOnlyMappingTransport(
        index_name=name, maximum=plan["mappingScanBudget"][f"{arm}EsHttp"])
    try:
        with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30,
                          trust_env=False, follow_redirects=False,
                          transport=transport) as client:
            return scan_b_mapping_arm_v1(output, arm=arm, git_state=_git_state(),
                                         client=client,
                                         observed_calls=lambda: transport.calls)
    finally:
        transport.close()


def _execute(output: Path, intent: bytes, fixture: bytes,
             mapping: bytes) -> dict[str, Any]:
    transports: dict[str, LimitedLocalTransport] = {}

    def client_factory(spec: CandidateSpec) -> httpx.Client:
        transport = LimitedLocalTransport(port=9200, maximum=spec.max_http_requests)
        transports["es"] = transport
        return httpx.Client(
            base_url="http://127.0.0.1:9200", timeout=30,
            trust_env=False, follow_redirects=False, transport=transport,
        )

    def preparation_factory(spec: CandidateSpec) -> LocalRepresentationVectorPreparationV1:
        transport = LimitedLocalTransport(port=8908, maximum=spec.max_embedding_requests)
        transports["bge"] = transport
        snapshot = json.loads(spec.model_snapshot)
        return LocalRepresentationVectorPreparationV1(
            spec, container=snapshot["container"]["id"], transport=transport,
        )

    def counts() -> tuple[int, int]:
        return (transports["es"].calls if "es" in transports else 0,
                transports["bge"].calls if "bge" in transports else 0)

    try:
        return execute_b_candidate_v1(
            output, intent, fixture, mapping, git_state=_git_state(),
            client_factory=client_factory, preparation_factory=preparation_factory,
            observed_counts=counts, execution_kind="local",
        )
    finally:
        for transport in transports.values():
            transport.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    scan_plan = modes.add_parser("plan-scans", help="freeze two read-only scan ceilings")
    scan_plan.add_argument("--preliminary-request", type=Path, required=True)
    scan_plan.add_argument("--assessment-intent", type=Path, required=True)
    scan_plan.add_argument("--uat-fixture", type=Path, required=True)
    scan_plan.add_argument("--output-directory", type=Path, required=True)
    for name in ("scan-source", "scan-candidate"):
        scan = modes.add_parser(name, help="one-shot bounded read-only physical ID scan")
        scan.add_argument("--output-directory", type=Path, required=True)
    freeze = modes.add_parser("freeze", help="local-only immutable CandidateSpec preflight")
    freeze.add_argument("--request", type=Path, required=True)
    freeze.add_argument("--assessment-intent", type=Path, required=True)
    freeze.add_argument("--uat-fixture", type=Path, required=True)
    freeze.add_argument("--id-mapping", type=Path, required=True)
    freeze.add_argument("--output-directory", type=Path, required=True)
    execute = modes.add_parser("execute", help="consume once and build a local ES candidate")
    execute.add_argument("--assessment-intent", type=Path, required=True)
    execute.add_argument("--uat-fixture", type=Path, required=True)
    execute.add_argument("--id-mapping", type=Path, required=True)
    execute.add_argument("--output-directory", type=Path, required=True)
    execute.add_argument("--execute-once", action="store_true", required=True)
    finalize = modes.add_parser("finalize-assessment", help="append post-build assessment without network")
    finalize.add_argument("--assessment-intent", type=Path, required=True)
    finalize.add_argument("--uat-fixture", type=Path, required=True)
    finalize.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    if args.mode in ("scan-source", "scan-candidate"):
        result = _scan(args.output_directory,
                       "source" if args.mode == "scan-source" else "candidate")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 0 if result["status"] == "scanned_read_only" else 1
    intent = _read(args.assessment_intent, 2 * 1024 * 1024)
    fixture = _read(args.uat_fixture, 2 * 1024 * 1024)
    if args.mode == "plan-scans":
        result = prepare_b_mapping_scans_v1(
            _read(args.preliminary_request, 2 * 1024 * 1024),
            intent, fixture, args.output_directory, git_state=_git_state(),
        )
    elif args.mode == "freeze":
        mapping = _read(args.id_mapping, 16 * 1024 * 1024)
        result = freeze_b_candidate_v1(
            _read(args.request, 2 * 1024 * 1024), intent, fixture, mapping,
            args.output_directory, git_state=_git_state(),
        )
    elif args.mode == "finalize-assessment":
        result = finalize_b_assessment_v2(
            args.output_directory, intent, fixture, git_state=_git_state(),
        )
    else:
        mapping = _read(args.id_mapping, 16 * 1024 * 1024)
        result = _execute(args.output_directory, intent, fixture, mapping)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return 0 if result["status"] in {
        "scan_plan_frozen_no_calls", "frozen_not_executed",
        "built_read_only_unpublished", "assessment_frozen"} else 1


if __name__ == "__main__":
    exit_code = 2
    try:
        exit_code = main()
    except BFreezeError as error:
        print(json.dumps({"status": "refused", "reason": error.reason}), flush=True)
    except Exception:
        print('{"status":"refused","reason":"driver_failed"}', flush=True)
    raise SystemExit(exit_code)
