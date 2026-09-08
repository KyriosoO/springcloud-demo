"""Deterministic scheduling for one frozen, synthetic process-exit diagnostic."""
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def isolate_frozen_exit_diagnostic_clock(request, monkeypatch):
    target = Path(__file__).with_name("test_employee_live_bootstrap_v2.py").resolve()
    if (Path(request.module.__file__).resolve() != target
            or request.node.name != "test_employee_v2_records_finite_diagnostic_then_deletes_raw_logs"):
        return
    from tests.integration.adapters import business_egress_live_bootstrap as bootstrap

    # This test checks an already-exited fake process, not readiness timing.
    # Keep its frozen 10 ms deadline and assertions; allow exactly two reads
    # before poll(). Never patch the global time module or any live runner.
    ticks = iter((0.0, 0.0))
    monkeypatch.setattr(bootstrap, "time", SimpleNamespace(monotonic=lambda: next(ticks)))
