from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from tests.integration.adapters import business_egress_live_bootstrap as bootstrap
from tests.integration.adapters.employee.conftest import isolate_frozen_exit_diagnostic_clock


NAME = "test_employee_v2_records_finite_diagnostic_then_deletes_raw_logs"


@pytest.mark.parametrize("filename,name,selected", [
    ("test_employee_live_bootstrap_v2.py", NAME, True),
    ("test_employee_live_bootstrap_v2.py", "test_employee_v2_without_live_authorization_has_zero_side_effects", False),
    ("test_employee_live_bootstrap_v1.py", NAME, False),
    ("../test_employee_live_bootstrap_v2.py", NAME, False),
])
def test_clock_is_exactly_scoped_and_restored(filename, name, selected, monkeypatch):
    request = SimpleNamespace(module=SimpleNamespace(__file__=str(Path(__file__).parent / filename)),
                              node=SimpleNamespace(name=name))
    original = bootstrap.time
    with monkeypatch.context() as patch:
        isolate_frozen_exit_diagnostic_clock.__wrapped__(request, patch)
        assert (bootstrap.time is not original) is selected
        assert time is original
        if selected:
            assert bootstrap.time.monotonic() == bootstrap.time.monotonic() == 0.0
            with pytest.raises(StopIteration):
                bootstrap.time.monotonic()
    assert bootstrap.time is original


@pytest.mark.parametrize("ticks,reason,polls", [((0.0, 0.011), "readiness_timeout", 0),
                                             ((0.0, 0.0), "process_exited", 1)])
def test_frozen_readiness_clock_priority_remains_unchanged(ticks, reason, polls, monkeypatch):
    calls = []
    clock = iter(ticks)
    process = SimpleNamespace(process=SimpleNamespace(poll=lambda: calls.append(1) or 1))
    def forbidden(*args, **kwargs):
        raise AssertionError("Already-exited synthetic process must not reach HTTP")
    with monkeypatch.context() as patch:
        patch.setattr(bootstrap, "time", SimpleNamespace(monotonic=lambda: next(clock)))
        patch.setattr(bootstrap.urllib.request, "urlopen", forbidden)
        with pytest.raises(bootstrap.BootstrapPhaseError, match=reason):
            bootstrap.LocalProcessRuntime.wait_http("http://127.0.0.1:1", process, port=1, deadline_seconds=0.01)
    assert len(calls) == polls
