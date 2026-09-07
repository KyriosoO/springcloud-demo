"""Historical compatibility belongs to the approved commit, not evolving source."""
import subprocess

import pytest

from tests.system_e2e import knowledge_stage_b_uat as old
from tests.system_e2e import knowledge_stage_b_uat_v7 as run07
from tests.system_e2e.conftest import frozen_run07_compatible_manifest


def test_fixture_uses_exact_approved_blobs_and_validator_still_rejects_current_source():
    value = frozen_run07_compatible_manifest()
    run07.validate_reuse(value)
    for name in run07.COMPATIBLE_CHANGES:
        source = subprocess.check_output(["git", "show", f"{run07.COMPATIBLE_HEAD}:{name}"], cwd=old.REPO)
        assert value["assets"][name] == old.digest(source)
    planner = "agent-runtime/src/agent_runtime/knowledge/semantic_planner.py"
    value["assets"][planner] = old.digest((old.REPO / planner).read_bytes())
    assert value["assets"][planner] != frozen_run07_compatible_manifest()["assets"][planner]
    with pytest.raises(ValueError, match="reuse_source_changed"):
        run07.validate_reuse(value)


def test_frozen_test_and_runner_bytes_not_modified():
    frozen_head = "806e1568c694a95769852a47e6c7ff00ec5b1f5a"
    for filename in ("test_knowledge_stage_b_uat_v7.py", "knowledge_stage_b_uat_v7.py"):
        name = "agent-runtime/tests/system_e2e/" + filename
        source = subprocess.check_output(["git", "show", f"{frozen_head}:{name}"], cwd=old.REPO)
        assert (old.REPO / name).read_bytes() == source
