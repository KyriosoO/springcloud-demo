from __future__ import annotations

from pathlib import Path

from tests.integration.adapters.business_egress_live_bootstrap import (
    load_strict_json,
    read_lifecycle,
    sha256_file,
    validate_prepared_assets,
    validate_result,
)
from tests.integration.adapters.transaction.live_bootstrap_v1 import (
    RUN_ID,
    authorization_path,
    candidate_output_paths,
    manifest_path,
    output_paths,
)


ROOT = Path(__file__).resolve().parents[5]
EXPECTED_SHA256 = {
    f"{RUN_ID}.manifest.json": (
        "c1a90bb90a0cf44b378f9bde1b1701f8de1321e75a9eae0c23d1a15f30d4c0d6"
    ),
    f"{RUN_ID}.authorization.json": (
        "b2b8d057afb1651cbb1b3ef098100846b30339da09ebbf2d7bb44ab705ae8308"
    ),
    f"{RUN_ID}.lifecycle.jsonl": (
        "a69fa805b9aa9b77035aa1f3c509195dd8a4e6ae0ed194ad2a58a8aa48f74891"
    ),
    f"{RUN_ID}.result.json": (
        "626ac18f8738cfe73dbeed9461e7cd21fa07edd9ec6911263a9177d64fc0a60a"
    ),
}


def test_transaction_bootstrap_failed_history_is_exact_and_non_reusable() -> None:
    evidence = manifest_path(ROOT).parent
    paths = {name: evidence / name for name in EXPECTED_SHA256}
    assert {name: sha256_file(path) for name, path in paths.items()} == EXPECTED_SHA256

    binding = validate_prepared_assets(
        repository_root=ROOT,
        manifest_path=manifest_path(ROOT),
        authorization_path=authorization_path(ROOT),
    )
    lifecycle_path, result_path = output_paths(ROOT)
    lifecycle = read_lifecycle(lifecycle_path, binding=binding)
    result = load_strict_json(result_path)
    validate_result(result, binding=binding)

    assert len(lifecycle) == 10
    assert lifecycle[-3] == {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "manifestSha256": EXPECTED_SHA256[f"{RUN_ID}.manifest.json"],
        "authorizationReference": "P3_00:GATE-026",
        "domain": "transaction",
        "sequence": 8,
        "phase": "auth_readiness",
        "status": "failed",
        "reason": "process_exited",
    }
    assert result == {
        "schemaVersion": 1,
        "runId": RUN_ID,
        "manifestSha256": EXPECTED_SHA256[f"{RUN_ID}.manifest.json"],
        "authorizationReference": "P3_00:GATE-026",
        "domain": "transaction",
        "status": "failed_pre_candidate_unconsumed",
        "candidateInvoked": False,
        "counts": {
            "candidateInvocations": 0,
            "phaseStarted": 5,
            "phaseTerminal": 5,
            "retry": 0,
            "resume": 0,
        },
        "safety": {
            "forbiddenFields": 0,
            "secretPersistence": 0,
            "logLeakCount": 0,
            "ownedProcessesStopped": True,
            "rawLogsDeleted": True,
        },
        "failure": {"phase": "auth_readiness", "reason": "process_exited"},
    }
    assert all(not path.exists() for path in candidate_output_paths(ROOT))
