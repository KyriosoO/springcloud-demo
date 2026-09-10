"""DR-KRET-036: disposable offline worker, never imported by production."""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

REVISION = "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
CACHE = Path("/root/.cache/huggingface/hub/models--BAAI--bge-reranker-v2-m3/snapshots") / REVISION
HASHES = {
    "model.safetensors": "d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286",
    "config.json": "13dcd6c31d9fec9d1d8e158702072f62d7fa7d312a64b9fe057bec9a08cfe41a",
    "sentencepiece.bpe.model": "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
    "special_tokens_map.json": "8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835",
    "tokenizer.json": "69564b696052886ed0ac63fa393e928384e0f8caada38c1f4864a9bfbf379c15",
    "tokenizer_config.json": "7e4c1cc848840aeccdd763458c18dd525eb0f795c992e00ebe9c28554e7db2d4",
}
CASES = tuple(f"KRB-{n:03}" for n in range(9, 13))


class ProbeError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise ProbeError(reason)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "invalid_json")
        result[key] = value
    return result


def reject_constant(value):
    raise ProbeError("invalid_json")


def decode(raw):
    return json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)


def validate_input(value):
    require(type(value) is dict and set(value) == {"cases"}, "invalid_input")
    cases = value["cases"]
    require(type(cases) is list and len(cases) == 4, "invalid_input")
    for case, expected in zip(cases, CASES):
        require(type(case) is dict and set(case) == {"caseId", "query", "documents"}
                and case["caseId"] == expected, "invalid_input")
        require(type(case["query"]) is str and 0 < len(case["query"]) <= 1024,
                "invalid_input")
        require(type(case["documents"]) is list and len(case["documents"]) == 20
                and all(type(s) is str and 0 < len(s) <= 4700 for s in case["documents"]),
                "invalid_input")
    return cases


def prepare(tokenizer, query, documents, window):
    """Exact installed FlagEmbedding token preparation, without its retries."""
    require(type(window) is int and window in (512, 1024), "invalid_window")
    query_ids = tokenizer(query, add_special_tokens=False)["input_ids"]
    require(len(query_ids) <= 384, "query_truncated")
    items = []
    for text in documents:
        doc_ids = tokenizer(text, add_special_tokens=False, max_length=window,
                            truncation=True)["input_ids"]
        item = tokenizer.prepare_for_model(query_ids, doc_ids, truncation="only_second",
                                           max_length=window, padding=False)
        require(0 < len(item["input_ids"]) <= window, "token_budget")
        items.append(item)
    return items


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def execute(value, emit):
    cases = validate_input(value)
    for name, expected in HASHES.items():
        require(file_hash(CACHE / name) == expected, "cache_changed")
    config = decode((CACHE / "config.json").read_bytes())
    require(config["max_position_embeddings"] >= 1026, "invalid_window")
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    require(torch.cuda.is_available(), "cuda_unavailable")
    tokenizer = AutoTokenizer.from_pretrained(str(CACHE), local_files_only=True,
                                               trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(str(CACHE),
        local_files_only=True, trust_remote_code=False).half().to("cuda:0").eval()
    emit({"event": "ready", "pid": os.getpid(), "modelHashes": HASHES,
          "torchVersion": str(torch.__version__), "dtype": "float16", "device": "cuda:0"})
    forwards = warmups = 0
    try:
        with torch.inference_mode():
            for window in (512, 1024):
                batch = tokenizer.pad(prepare(tokenizer, "synthetic check",
                    ["synthetic document " * 1000], window), padding=True,
                    return_tensors="pt").to("cuda:0")
                warmups += 1
                model(**batch, return_dict=True)
                torch.cuda.synchronize()
            emit({"event": "warmup", "warmupForwards": warmups})
            for ordinal, case in enumerate(cases):
                for window in ((512, 1024) if ordinal % 2 == 0 else (1024, 512)):
                    items = prepare(tokenizer, case["query"], case["documents"], window)
                    # Match length-sorted batching; stable tie order is explicit.
                    order = sorted(range(20), key=lambda i: (-len(items[i]["input_ids"]), i))
                    scores = [0.0] * 20
                    torch.cuda.reset_peak_memory_stats()
                    torch.cuda.synchronize()
                    started = time.monotonic()
                    for start in range(0, 20, 2):
                        indices = order[start:start + 2]
                        batch = tokenizer.pad([items[i] for i in indices], padding=True,
                                               return_tensors="pt").to("cuda:0")
                        forwards += 1
                        require(forwards <= 80, "forward_budget")
                        logits = model(**batch, return_dict=True).logits.view(-1).float()
                        values = logits.cpu().tolist()
                        require(len(values) == 2 and all(math.isfinite(x) for x in values),
                                "invalid_score")
                        for index, logit in zip(indices, values):
                            scores[index] = (1 / (1 + math.exp(-logit)) if logit >= 0
                                             else math.exp(logit) / (1 + math.exp(logit)))
                    torch.cuda.synchronize()
                    emit({"event": "arm", "caseId": case["caseId"], "window": window,
                          "scores": scores, "tokens": [len(i["input_ids"]) for i in items],
                          "durationMs": round((time.monotonic() - started) * 1000),
                          "peakAllocatedBytes": torch.cuda.max_memory_allocated(),
                          "forwards": 10})
        emit({"event": "complete", "forwards": forwards, "warmupForwards": warmups})
    except Exception as exc:
        reason = (str(exc) if type(exc) is ProbeError else
                  "cuda_oom" if isinstance(exc, torch.cuda.OutOfMemoryError) else "inference_failed")
        emit({"event": "failed", "reason": reason, "forwards": forwards,
              "warmupForwards": warmups})
        return 1
    return 0


def main():
    def emit(value):
        print(json.dumps(value, allow_nan=False, separators=(",", ":")),
              file=sys.__stdout__, flush=True)
    try:
        raw = sys.stdin.buffer.read(1024 * 1024 + 1)
        require(len(raw) <= 1024 * 1024, "invalid_input")
        value = decode(raw)
        # Third-party logs never enter output or a raw log file.
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return execute(value, emit)
    except Exception as exc:
        emit({"event": "failed", "reason": str(exc) if type(exc) is ProbeError else "preparation_failed",
              "forwards": 0, "warmupForwards": 0})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
