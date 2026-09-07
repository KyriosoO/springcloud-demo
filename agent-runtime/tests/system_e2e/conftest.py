"""Test-only historical inputs; consumed runners and validators stay immutable."""
from __future__ import annotations

import subprocess

import pytest


def frozen_run07_compatible_manifest():
    from tests.system_e2e import knowledge_stage_b_uat as old
    from tests.system_e2e import knowledge_stage_b_uat_v7 as run07

    value, _ = run07.run06_assets()
    for name in run07.COMPATIBLE_CHANGES:
        source = subprocess.check_output(
            ["git", "show", f"{run07.COMPATIBLE_HEAD}:{name}"], cwd=old.REPO,
        )
        value["assets"][name] = old.digest(source)
    return value


@pytest.fixture(autouse=True)
def isolate_consumed_run07_test_input(request, monkeypatch):
    # Only replace fixture preparation, never a validator, assertion or live runner.
    if request.module.__name__ == "tests.system_e2e.test_knowledge_stage_b_uat_v7":
        monkeypatch.setattr(request.module, "compatible_manifest", frozen_run07_compatible_manifest)
