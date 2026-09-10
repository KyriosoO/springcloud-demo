"""UAT_01 14.45: one bounded local window comparison, never paid/live UAT."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date
import json
import math
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import uuid

from agent_runtime.knowledge.retrieval.bge_rerank_context import authorized_scoring_text
from tests.evaluation.knowledge import retrieval_relevance_review as review
from tests.evaluation.knowledge.retrieval_metrics import RelevanceGrade, SourceRef, score_retrieval
from tests.system_e2e import knowledge_evidence_source_replay_v1 as source
from tests.system_e2e import knowledge_rerank_window_worker_v1 as worker

REPO = source.REPO
CONTAINER = "bge-reranker-v2-m3-service"
CONTAINER_ID = "f3580525d8948b67e2d26759cc4f3ed2cf83cebd440e8da4b6b63e51c71a27dc"
IMAGE_ID = "sha256:322c5a46791681b021194dd02633fb701c91130a95e89cecd7ecad4ef157468d"
RESULT = Path("D:/codex-data/knowledge-rerank-window-20260910-v1.jsonl")
WORKER = Path(worker.__file__)
LIMIT = 65536
VISIBILITY_SHA = "b73bc47205cd364cb25cd68be3ffe332268e68118ebb0a46fa27a3885dd2958e"
REVIEW_SHA = "d64b298fc18067be448feeecae51c1614e9a6e2226a102faaa809d871158d593"
REASONS = {"invalid_json", "invalid_input", "invalid_window", "query_truncated", "token_budget",
           "cache_changed", "cuda_unavailable", "forward_budget", "invalid_score", "cuda_oom",
           "inference_failed", "preparation_failed", "worker_timeout", "worker_alive",
           "worker_output_invalid", "container_changed", "execution_failed", "input_changed"}
require = worker.require


def container_identity():
    result = subprocess.run(["docker", "inspect", "--format", "{{.Id}} {{.Image}}", CONTAINER],
                            capture_output=True, timeout=10, check=False)
    require(result.returncode == 0 and result.stdout.decode().strip() == f"{CONTAINER_ID} {IMAGE_ID}",
            "container_changed")


def worker_alive(tag):
    # Only report our exact argv marker, never expose other process arguments.
    code = """import os,sys
from pathlib import Path
found=False
for p in Path('/proc').iterdir():
 if not p.name.isdecimal() or int(p.name)==os.getpid(): continue
 try: args=(p/'cmdline').read_bytes().split(b'\\0')
 except (FileNotFoundError,ProcessLookupError,PermissionError): continue
 if args and args[-1]==b'': args.pop()
 if args and args[-1]==sys.argv[1].encode(): found=True
print(int(found))
"""
    result = subprocess.run(["docker", "exec", CONTAINER, "python", "-c", code, tag],
                            capture_output=True, timeout=10, check=False)
    require(result.returncode == 0 and result.stdout.strip() in (b"0", b"1"), "worker_alive")
    return result.stdout.strip() == b"1"


def run_worker(payload, tag):
    command = ["docker", "exec", "-i", CONTAINER, "timeout", "--signal=TERM", "--kill-after=5s",
               "300s", "python", "-B", "-c", WORKER.read_text(encoding="utf-8"), tag]
    collected = bytearray()
    overflow = False
    io_failed = False
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    def drain():
        nonlocal overflow, io_failed
        try:
            while chunk := process.stdout.read(4096):
                available = LIMIT - len(collected)
                collected.extend(chunk[:available])
                overflow |= len(chunk) > available
        except OSError:
            io_failed = True
    def supply():
        nonlocal io_failed
        try:
            process.stdin.write(source.canonical(payload))
            process.stdin.close()
        except OSError:
            io_failed = True
    reader = threading.Thread(target=drain, daemon=True)
    writer = threading.Thread(target=supply, daemon=True)
    reader.start()
    writer.start()
    try:
        process.wait(timeout=315)
    except subprocess.TimeoutExpired:
        raise worker.ProbeError("worker_timeout") from None
    finally:
        # Never use Popen.__exit__'s unbounded wait, including on a broken stdin.
        # Kill only this host-side client. Container timeout owns its worker.
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        writer.join(timeout=5)
        reader.join(timeout=5)
        if not writer.is_alive():
            process.stdin.close()
        if not reader.is_alive():
            process.stdout.close()
    require(not reader.is_alive() and not writer.is_alive() and not overflow and not io_failed,
            "worker_output_invalid")
    return process.returncode, bytes(collected)


def checked_events(raw):
    require(type(raw) is bytes and 0 < len(raw) <= LIMIT, "worker_output_invalid")
    events = [worker.decode(line) for line in raw.splitlines()]
    require(1 <= len(events) <= 11, "worker_output_invalid")
    seen, total = set(), 0
    for i, event in enumerate(events):
        require(type(event) is dict, "worker_output_invalid")
        kind = event.get("event")
        if kind == "ready":
            require(i == 0 and set(event) == {"event", "pid", "modelHashes", "torchVersion", "dtype", "device"}
                    and type(event["pid"]) is int and event["pid"] > 0
                    and event["modelHashes"] == worker.HASHES and event["dtype"] == "float16"
                    and event["device"] == "cuda:0" and type(event["torchVersion"]) is str
                    and len(event["torchVersion"]) < 40, "worker_output_invalid")
        elif kind == "warmup":
            require(i == 1 and set(event) == {"event", "warmupForwards"}
                    and type(event["warmupForwards"]) is int and event["warmupForwards"] == 2,
                    "worker_output_invalid")
        elif kind == "arm":
            require(set(event) == {"event", "caseId", "window", "scores", "tokens", "durationMs",
                                  "peakAllocatedBytes", "forwards"}, "worker_output_invalid")
            key = (event["caseId"], event["window"])
            expected = [(c, w) for n, c in enumerate(worker.CASES)
                        for w in ((512, 1024) if n % 2 == 0 else (1024, 512))]
            require(2 <= i <= 9 and key == expected[i - 2] and key not in seen
                    and type(event["window"]) is int, "worker_output_invalid")
            seen.add(key)
            for field in ("scores", "tokens"):
                require(type(event[field]) is list and len(event[field]) == 20, "worker_output_invalid")
            require(all(type(x) in (int, float) and math.isfinite(x) and 0 <= x <= 1 for x in event["scores"])
                    and all(type(x) is int and 0 < x <= event["window"] for x in event["tokens"])
                    and type(event["forwards"]) is int and event["forwards"] == 10
                    and type(event["durationMs"]) is int and 0 <= event["durationMs"] <= 300000
                    and type(event["peakAllocatedBytes"]) is int and 0 < event["peakAllocatedBytes"] <= 16 * 1024**3,
                    "worker_output_invalid")
            total += 10
        elif kind in ("failed", "complete"):
            require(i == len(events) - 1 and set(event) == ({"event", "reason", "forwards", "warmupForwards"}
                        if kind == "failed" else {"event", "forwards", "warmupForwards"}), "worker_output_invalid")
            require(type(event["forwards"]) is int and total <= event["forwards"] <= 80
                    and type(event["warmupForwards"]) is int and 0 <= event["warmupForwards"] <= 2,
                    "worker_output_invalid")
            if kind == "failed":
                require(event["reason"] in REASONS, "worker_output_invalid")
                require((i == 0 and event["forwards"] == event["warmupForwards"] == 0)
                        or (i == 1 and event["forwards"] == 0)
                        or (i >= 2 and event["warmupForwards"] == 2
                            and event["forwards"] <= min(total + 10, 80)), "worker_output_invalid")
            else:
                require(i == 10 and len(seen) == 8 and event["forwards"] == 80
                        and event["warmupForwards"] == 2, "worker_output_invalid")
        else:
            raise worker.ProbeError("worker_output_invalid")
    require(events[-1]["event"] in ("complete", "failed"), "worker_output_invalid")
    return events


def select_inputs(rows, dataset, pool):
    selected = [c for c in dataset.cases if c.id in worker.CASES]
    saved = {r["caseId"]: r for r in rows if r.get("event") == "case" and r["caseId"] in worker.CASES}
    require(tuple(c.id for c in selected) == worker.CASES
            and all(c.split == "development" and len(c.requirements) == 1 for c in selected), "input_changed")
    subset = {v["chunkId"]: pool[v["chunkId"]] for c in selected for v in saved[c.id]["ranked"]}
    require(len(subset) == 70 and all(len(saved[c.id]["ranked"]) == 20 for c in selected), "input_changed")
    return selected, saved, subset


def payload_for(cases, saved, sources, pool, profiles):
    result = []
    for case in cases:
        documents = []
        for item in saved[case.id]["ranked"]:
            s = sources[item["chunkId"]]
            profile = profiles["tax-policy-v1" if pool[item["chunkId"]][1] == "tax.policy" else "tax-law-v1"]
            require(s["channel"] in profile["category-values"], "input_changed")
            documents.append(authorized_scoring_text(SimpleNamespace(content=s["content"], title=s.get("title"),
                document_number=s.get("documentNo"), written_date=date.fromisoformat(s["writtenDate"]) if s.get("writtenDate") else None)))
        result.append({"caseId": case.id, "query": case.requirements[0].focus, "documents": documents})
    value = {"cases": result}
    worker.validate_input(value)
    return value


def measure(events, cases, saved, dataset, rows):
    # Grading is post-inference only; never included in worker input.
    review.evaluate_review()
    grades = {r["caseId"]: r["judgments"] for r in [review.decode(line) for line in review.PATH.read_bytes().splitlines()]
              if r["event"] == "case_review"}
    source_ids = {s.id: SourceRef(s.chunk_id, s.sha256) for s in dataset.sources}
    results = []
    for case in cases:
        values = [SourceRef(v["chunkId"], v["sha256"]) for v in saved[case.id]["ranked"]]
        qrels = tuple(RelevanceGrade(SourceRef(v["chunkId"], v["sha256"]), v["grade"]) for v in grades[case.id])
        grade_map = {g.source: g.grade for g in qrels}
        old = next(r for r in rows if r.get("caseId") == case.id and r.get("stage") == "rerank")
        old_scores = {v["chunkId"]: v["score"] for v in old["candidates"]}
        for arm in (e for e in events if e.get("caseId") == case.id):
            order = sorted(range(20), key=lambda i: (-arm["scores"][i], i))
            ranked = tuple(values[i] for i in order)
            metrics = score_retrieval(corpus_state="present", k=20, ranked=ranked, evidence=ranked[:8],
                required_groups=tuple((source_ids[s],) for s in case.sources), grades=qrels)
            results.append({"event": "metrics", "caseId": case.id, "window": arm["window"],
                "metrics": asdict(metrics), "top8Relevant": sum(grade_map[s] > 0 for s in ranked[:8]),
                "top8Direct": sum(grade_map[s] >= 2 for s in ranked[:8]),
                "maxSavedScoreDelta": max(abs(arm["scores"][i] - old_scores[s.chunk_id]) for i, s in enumerate(values)),
                "sameSavedTop1": ranked[0] == values[0],
                "ranked": [{"chunkId": s.chunk_id, "sha256": s.sha256} for s in ranked]})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    if not parser.parse_args().execute:
        parser.error("explicit --execute required")
    terminal = {"event": "terminal", "status": "failed", "reason": None, "externalModelCalls": 0,
                "indexWrites": 0, "sourceReads": 0, "snapshotReads": 0, "workerStopped": None,
                "forwards": 0, "warmupForwards": 0, "scorePairs": 0, "counterStatus": "confirmed"}
    reader = snapshots = None
    tag = "knowledge-window-" + uuid.uuid4().hex
    started_worker = False
    with RESULT.open("xb") as stream:
        emit = lambda value: source.base.emit_line(stream, value)
        try:
            head = source.base.clean_head()
            rows, dataset, pool, profiles = source.load_inputs()
            require(source.digest(review.PATH.read_bytes()) == REVIEW_SHA, "input_changed")
            require(source.digest((review.DIRECTORY / "rerank_token_visibility.v1.json").read_bytes()) == VISIBILITY_SHA,
                    "input_changed")
            cases, saved, subset = select_inputs(rows, dataset, pool)
            emit({"event": "prepared", "head": head, "datasetSha256": dataset.sha256,
                  "resultSha256": source.SAVED_SHA, "reviewSha256": REVIEW_SHA,
                  "workerSha256": source.digest(WORKER.read_bytes()), "hostSha256": source.digest(Path(__file__).read_bytes()),
                  "sourcePool": subset, "containerId": CONTAINER_ID, "imageId": IMAGE_ID,
                  "modelHashes": worker.HASHES, "sourceReadBudget": 7, "snapshotReadBudget": 6,
                  "forwardsBudget": 80, "warmupBudget": 2})
            container_identity()
            support = source.base.load_support()
            binding = worker.decode(support.checked_bytes(REPO / "serviceCenter/knowledge-runtime-binding.v2.json", source.base.BINDING_SHA))
            snapshots = source.SnapshotReader(support, binding)
            source.base.check_index(snapshots, binding)
            reader = source.SourceReader(support, binding, 7)
            sources = {}
            ids = sorted(subset)
            for start in range(0, 70, 10):
                sources.update(reader.read_pool({k: subset[k] for k in ids[start:start + 10]}))
            payload = payload_for(cases, saved, sources, subset, profiles)
            emit({"event": "worker_started", "workerTag": tag})
            started_worker = True
            # Lost/truncated worker output means unknown attempts, never zero.
            terminal.update(forwards=None, warmupForwards=None, scorePairs=None, counterStatus="unknown")
            code, raw = run_worker(payload, tag)
            events = checked_events(raw)
            for event in events:
                emit(event)
            terminal.update(forwards=events[-1]["forwards"], warmupForwards=events[-1]["warmupForwards"],
                            counterStatus="confirmed")
            require(code == 0 and events[-1]["event"] == "complete", "inference_failed")
            source.base.check_index(snapshots, binding)
            container_identity()
            source.base.clean_head(head)
            for metrics in measure(events, cases, saved, dataset, rows):
                emit(metrics)
            terminal.update(status="measured", forwards=80, warmupForwards=2, scorePairs=160)
        except Exception as exc:
            terminal["reason"] = str(exc) if type(exc) is worker.ProbeError and str(exc) in REASONS else "execution_failed"
        finally:
            if started_worker:
                try:
                    terminal["workerStopped"] = not worker_alive(tag)
                except Exception:
                    terminal["workerStopped"] = False
                if terminal["workerStopped"] is not True:
                    terminal.update(status="failed", reason="worker_alive")
            else:
                terminal["workerStopped"] = True
            terminal.update(sourceReads=reader.reads if reader else 0, snapshotReads=snapshots.reads if snapshots else 0)
            emit(terminal)
    print(json.dumps(terminal), flush=True)
    return 0 if terminal["status"] == "measured" else 1


if __name__ == "__main__":
    raise SystemExit(main())
