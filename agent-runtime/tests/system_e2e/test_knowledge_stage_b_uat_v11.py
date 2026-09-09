"""Offline Java preflight binding and unconsumed history checks."""
from copy import deepcopy
import os
from types import SimpleNamespace

import pytest

from tests.system_e2e import knowledge_stage_b_uat_v11 as new


@pytest.mark.parametrize("version", [b'openjdk version "25.0.2"', b'java version "1.8.0_503"', b'unknown'])
def test_version_checked_before_any_services(tmp_path, monkeypatch, version):
    binary = tmp_path / "bin/java.exe"
    binary.parent.mkdir(); binary.write_bytes(b"synthetic-java")
    monkeypatch.setattr(new, "JAVA_ROOT", tmp_path)
    monkeypatch.setattr(new.shutil, "which", lambda _: str(binary))
    monkeypatch.setattr(new.subprocess, "run", lambda *a, **k: SimpleNamespace(stderr=version))
    if version.startswith(b"openjdk"):
        assert new.java_binding()["version"] == "25.0.2"
    else:
        with pytest.raises(ValueError, match="java_version_invalid"): new.java_binding()


def test_wrong_resolution_rejected_before_version_process(monkeypatch):
    monkeypatch.setattr(new.shutil, "which", lambda _: "C:/untrusted/java.exe")
    monkeypatch.setattr(new.subprocess, "run", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(ValueError, match="java_resolution_invalid"): new.java_binding()


@pytest.mark.parametrize("fail", [True, False])
def test_child_environment_restores_even_preflight_failure(monkeypatch, fail):
    before = {key: os.environ.get(key) for key in ("PATH", "JAVA_HOME")}
    def validate():
        assert os.environ["JAVA_HOME"] == str(new.JAVA_ROOT)
        assert os.environ["PATH"].startswith(str(new.JAVA_ROOT / "bin") + os.pathsep)
        if fail: raise ValueError("stage_b.java_version_invalid")
    monkeypatch.setattr(new, "java_binding", validate)
    with pytest.raises(ValueError):
        with new.java_environment():
            assert not fail
            raise ValueError("synthetic-test-exit")
    assert {key: os.environ.get(key) for key in before} == before


def test_manifest_java_history_budget_and_frozen_old_files(tmp_path, monkeypatch):
    base = dict(priorRuns=new.previous.prior_bindings(), limits=new.previous.previous.LIMITS,
                startupLimits=dict(rerank=1))
    monkeypatch.setattr(new, "_manifest", lambda root: deepcopy(base))
    monkeypatch.setattr(new, "java_binding", lambda: dict(version="25.0.2", sha256="a" * 64))
    result = new.current_manifest(tmp_path)
    assert result["schemaVersion"] == 11 and result["javaBinding"]["version"] == "25.0.2"
    assert result["failedPreflight"]["hashes"] == new.HASHES
    assert result["failedPreflight"]["model"] == 0
    with new.overrides():
        assert new.current_manifest(tmp_path)["failedPreflight"]["runId"] == "knowledge-stage-b-uat-v10-20260909-run-10"
    assert not (new.PREFLIGHT_ROOT / "consumed.json").exists()
    with monkeypatch.context() as scoped:
        scoped.setattr(new, "TOTAL_LIMITS", {**new.TOTAL_LIMITS, "rerank": 48})
        with pytest.raises(ValueError, match="cumulative_budget_invalid"): new.current_manifest(tmp_path)


def test_new_bindings_and_restore():
    old = (new.previous.RUN_ID, new.previous.previous.RUN_ID, new.previous.current_manifest)
    with new.overrides(), new.previous.previous.bindings():
        assert new.legacy.RUN_ID == new.RUN_ID
        assert new.previous.previous.current_manifest is new.current_manifest
        assert new.previous.previous.TOTAL_LIMITS["rerank"] == 49
    assert old == (new.previous.RUN_ID, new.previous.previous.RUN_ID, new.previous.current_manifest)
