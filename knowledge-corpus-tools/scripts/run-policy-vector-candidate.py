"""One-shot DR-KRET-031 candidate build. No alias changes or external LLM."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import httpx

from knowledge_corpus_tools.jsonio import exclusive_write
from knowledge_corpus_tools.local_vector_preparation import LocalVectorPreparation
from knowledge_corpus_tools.vector_candidate import (
    CandidateError, VectorCandidateSpec, _reject_constant, _unique_pairs,
    build_policy_vector_candidate, canonical_bytes,
)


class CountedTransport(httpx.HTTPTransport):
    def __init__(self) -> None:
        super().__init__(retries=0, trust_env=False)
        self.calls = 0

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        return super().handle_request(request)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-binding", required=True, type=Path)
    parser.add_argument("--container", required=True)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    output = args.output_directory.resolve()
    # Refuse reuse before probing a model or contacting ES.
    if output.exists():
        print('{"status":"refused","reason":"output_exists"}')
        return 2
    status = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                            capture_output=True, check=True)
    if status.stdout:
        print('{"status":"refused","reason":"worktree_not_clean"}')
        return 2
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                          capture_output=True, text=True, check=True).stdout.strip()
    source_raw = args.source_binding.read_bytes()
    source = json.loads(source_raw, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)
    preparation = LocalVectorPreparation(args.container)
    snapshot = preparation.freeze()
    spec = VectorCandidateSpec(**source, model_snapshot_sha256=preparation.snapshot_sha256)
    binding = {"schemaVersion": 1, "sourceCommit": head, "spec": asdict(spec),
               "sourceBindingSha256": hashlib.sha256(source_raw).hexdigest(),
               "modelSnapshot": snapshot, "budgets": {"esHttp": 400, "embeddingHttp": 32,
               "embeddingTexts": 1000, "paid": 0, "retry": 0, "resume": 0, "aliasWrites": 0}}
    exclusive_write(output / "binding.json", canonical_bytes(binding))
    started = time.monotonic()
    transport = CountedTransport()
    terminal: dict[str, object] = {"schemaVersion": 1, "status": "failed",
                                  "candidate": spec.candidate_index}
    print('{"phase":"source_validation_and_model_preparation"}', flush=True)
    interrupted = False
    try:
        with httpx.Client(base_url="http://127.0.0.1:9200", timeout=30, trust_env=False,
                          follow_redirects=False, transport=transport) as client:
            result = build_policy_vector_candidate(spec, client=client, prepare_vectors=preparation)
        terminal.update(status="built_read_only_unpublished", result=asdict(result))
    except CandidateError as error:
        terminal.update(reason=error.reason, phase=error.phase, sealStatus=error.seal_status)
    except KeyboardInterrupt as error:
        # Builder emits only a finite cleanup note, never the HTTP exception text.
        note = next((n for n in getattr(error, "__notes__", []) if n in {
            "candidate_cleanup:not_needed", "candidate_cleanup:sealed",
            "candidate_cleanup:candidate_seal_failed"}), "candidate_cleanup:candidate_seal_failed")
        terminal.update(reason="cancelled", sealStatus=note.split(":")[1])
        interrupted = True
    except Exception:
        terminal.update(reason="driver_failed", sealStatus="unknown")
    terminal.update(esHttp=transport.calls, embeddingHttp=preparation.http_calls,
                    embeddingTexts=preparation.text_count, maxTokens=preparation.max_tokens,
                    preparationFailure=preparation.failure_reason, paid=0, retry=0, resume=0,
                    aliasWrites=0, elapsedSeconds=round(time.monotonic() - started, 2),
                    bindingSha256=hashlib.sha256(canonical_bytes(binding)).hexdigest())
    exclusive_write(output / "result.json", canonical_bytes(terminal))
    print(json.dumps(terminal, ensure_ascii=False, sort_keys=True), flush=True)
    return 130 if interrupted else (0 if terminal["status"] == "built_read_only_unpublished" else 1)


if __name__ == "__main__":
    # CLI errors before binding must not disclose raw model/process/HTTP data.
    exit_code = 2
    try:
        exit_code = main()
    except Exception:
        print('{"status":"refused","reason":"preflight_or_evidence_io_failed"}')
    raise SystemExit(exit_code)
