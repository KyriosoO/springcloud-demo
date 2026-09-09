"""Immutable finite run-11 result; current source is allowed to evolve."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).with_name("knowledge_stage_b_run_11")
HASHES = {
    "manifest.json": "56c3fc8b1d312e734a5ca13ed38390869befb8222673ddff7c70fb3c534b2807",
    "authorization.json": "d849fc9b42e15117270bd75ac8495c4ec8cdad4021f081d65887b1eadad93482",
    "consumed.json": "e4e16b241f8f67afc0ce79d965812b9504a28206333de42aa544fe335505f89c",
    "journal.jsonl": "ffac99686b316c68e34fe7d3a7ace3cc16409a79ba5c54ec422f6d1ef4f8a3d3",
    "result.json": "2025550720405361a79d659cf02dc500dfb5561c983171d6b7bd5cf01e0d0392",
    "evidence.jsonl": "015400be6363a7864112bb812d8de54cdd4014aee66f387f9722c40eca020755",
    "startup.jsonl": "27175f818a79d536b0e9cf3948f3de87955295428751d5054705eb9305c00ffc",
    "environment.jsonl": "753c395c33e04976b05598a87d25ff00503cf5c174ac6bebd94665ad39d90ddf",
}


def test_exact_original_bytes_and_consumed_failure():
    assert {p.name for p in ROOT.iterdir()} == set(HASHES)
    for name, sha in HASHES.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha
    manifest = json.loads((ROOT / "manifest.json").read_bytes())
    assert manifest["frozenHead"] == "09413f7bf0a0b3d34476b76b9db7571fbeb9b21e"
    result = json.loads((ROOT / "result.json").read_bytes())
    assert result["status"] == "failed"
    assert result["totals"] == dict(e2e=2, model=5, search=2, embedding=1, rerank=1, business=0, retry=0, resume=0)
    assert len((ROOT / "journal.jsonl").read_bytes().splitlines()) == 5
