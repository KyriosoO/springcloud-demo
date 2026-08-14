from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from agent_runtime.capability_api.contracts import (
    CapabilityResult,
    CapabilityStatus,
    EgressDisposition,
    FailureDetail,
    FailureSource,
    JsonValue,
    ModelEgressResult,
)
from tests.integration.adapters.employee.egress_input_qualification import (
    InputQualificationError,
    QualificationReason,
    QualificationSelectionMode,
    QualificationStatus,
    build_input_qualification_evidence,
    build_qualification_probe,
    validate_input_qualification_evidence,
    validate_qualification_probe,
)


def _success(*, position: str | None, work_base_si: str | None) -> CapabilityResult:
    fields: dict[str, JsonValue] = {
        "employee_id_masked": "********0000",
        "chinese_name": "synthetic",
    }
    if position is not None:
        fields["position"] = position
    if work_base_si is not None:
        fields["work_base_si"] = work_base_si
    allowed = bool(position and position.strip() and work_base_si and work_base_si.strip())
    return CapabilityResult(
        status=CapabilityStatus.SUCCESS,
        domain_result={
            "schema_version": 1,
            "capability_id": "employee.detail",
            "records": ({"record_ref": "record-0001", "fields": fields},),
            "coverage": {"returned_count": 1, "truncated": False, "total_count": 1},
        },
        egress=ModelEgressResult(
            disposition=EgressDisposition.ALLOWED if allowed else EgressDisposition.DENIED,
            policy_version="business-egress-v1",
            safe_payload=(
                {
                    "schema_version": 1,
                    "facts": (
                        {"source": {"field_id": "position"}},
                        {"source": {"field_id": "work_base_si"}},
                    ),
                }
                if allowed
                else None
            ),
            reason_code=None if allowed else "business.no_model_fields",
        ),
        failure=None,
    )


def test_qualified_probe_and_final_evidence_are_exact_and_value_free() -> None:
    probe = build_qualification_probe(
        selection_mode=QualificationSelectionMode.READ_ONLY_DATABASE,
        result=_success(position="synthetic-position", work_base_si="synthetic-location"),
        database_selection_rows=1,
        employee_detail_requests=1,
    )
    evidence = build_input_qualification_evidence(
        probe,
        raw_logs_deleted=True,
        log_leak_count=0,
    )

    assert evidence["status"] == QualificationStatus.QUALIFIED
    assert evidence["egressReason"] == QualificationReason.QUALIFIED
    assert evidence["fieldPresence"] == {"position": True, "workBaseSi": True}
    encoded = json.dumps(evidence, ensure_ascii=False)
    assert "synthetic-position" not in encoded
    assert "synthetic-location" not in encoded
    assert validate_input_qualification_evidence(evidence) is evidence


def test_missing_field_is_not_qualified_without_model_call() -> None:
    probe = build_qualification_probe(
        selection_mode=QualificationSelectionMode.MAINTAINER_CONFIRMED,
        result=_success(position=None, work_base_si="synthetic-location"),
        database_selection_rows=0,
        employee_detail_requests=1,
    )

    assert probe == {
        "selectionMode": "maintainer_confirmed",
        "status": "not_qualified",
        "fieldPresence": {"position": False, "workBaseSi": True},
        "egressReason": "business.no_model_fields",
        "requestCounts": {
            "databaseSelectionRows": 0,
            "employeeDetail": 1,
            "otherEmployeeEndpoints": 0,
            "model": 0,
        },
    }


def test_downstream_failure_maps_to_finite_request_failed_reason() -> None:
    result = CapabilityResult(
        status=CapabilityStatus.DOWNSTREAM_FAILURE,
        domain_result=None,
        egress=ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE),
        failure=FailureDetail(
            code="business.downstream_failure",
            source=FailureSource.DOWNSTREAM,
        ),
    )
    probe = build_qualification_probe(
        selection_mode=QualificationSelectionMode.READ_ONLY_DATABASE,
        result=result,
        database_selection_rows=1,
        employee_detail_requests=1,
    )

    assert probe["status"] == "failed"
    assert probe["egressReason"] == "employee.request_failed"


def _add_extra(item: dict[str, Any]) -> None:
    item["extra"] = True


def _set_position_to_string(item: dict[str, Any]) -> None:
    cast(dict[str, Any], item["fieldPresence"])["position"] = "true"


def _set_model_call(item: dict[str, Any]) -> None:
    cast(dict[str, Any], item["requestCounts"])["model"] = 1


def _set_key_read(item: dict[str, Any]) -> None:
    cast(dict[str, Any], item["safety"])["llmApiKeyRead"] = True


def _set_logs_retained(item: dict[str, Any]) -> None:
    cast(dict[str, Any], item["safety"])["rawLogsDeleted"] = False


@pytest.mark.parametrize(
    "mutate",
    [_add_extra, _set_position_to_string, _set_model_call, _set_key_read, _set_logs_retained],
)
def test_strict_evidence_rejects_extra_wrong_type_or_nonzero_safety(
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    probe = build_qualification_probe(
        selection_mode=QualificationSelectionMode.READ_ONLY_DATABASE,
        result=_success(position="synthetic-position", work_base_si="synthetic-location"),
        database_selection_rows=1,
        employee_detail_requests=1,
    )
    evidence = build_input_qualification_evidence(probe, raw_logs_deleted=True, log_leak_count=0)
    copied = cast(dict[str, Any], json.loads(json.dumps(evidence)))
    mutate(copied)

    with pytest.raises(InputQualificationError, match="employee.egress_input_qualification_invalid"):
        validate_input_qualification_evidence(copied)


def test_schema_has_exact_top_level_and_safety_fields() -> None:
    path = (
        Path(__file__).parent
        / "evidence"
        / "employee-egress-input-qualification-v1.schema.json"
    )
    schema = json.loads(path.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["safety"]["additionalProperties"] is False
    assert schema["properties"]["requestCounts"]["properties"]["model"] == {"const": 0}


def test_probe_rejects_zero_detail_without_no_candidate_reason() -> None:
    probe = {
        "selectionMode": "read_only_database",
        "status": "failed",
        "fieldPresence": {"position": False, "workBaseSi": False},
        "egressReason": "employee.request_failed",
        "requestCounts": {
            "databaseSelectionRows": 0,
            "employeeDetail": 0,
            "otherEmployeeEndpoints": 0,
            "model": 0,
        },
    }
    with pytest.raises(InputQualificationError):
        validate_qualification_probe(probe)


def test_launcher_binds_exact_history_and_removes_model_key() -> None:
    repository = Path(__file__).parents[4]
    launcher = (
        repository / "scripts" / "run-employee-egress-input-qualification.ps1"
    ).read_text(encoding="utf-8")
    expected = {
        "employee-egress-v1-20260813-candidate-01.manifest.json":
            "c3cdfacd32797474f68e11758ec094df97a95d56fb0efed9355ccfaa6a145c57",
        "employee-egress-v1-20260813-candidate-01.authorization.json":
            "52b9075117f3e5f3ea84f1ea3c5da846c7b168f013fc4d8523d7ed52979f416c",
        "wp-emp-egress-env-diag-01-20260814T004517Z.json":
            "2bc16cf63f3775d778925a5a5a66cfbae5138401e2f209e8288f4db076598a2c",
        "employee-egress-v1-20260813-candidate-01.pre-model-failure-20260814T005222Z.json":
            "1a55b324fc912ee4e9133c2946183473347eb8e7f3337f8e33286bdf96f0b76f",
        "employee-egress-v2-20260814-candidate-02.manifest.json":
            "28cd7b04b0700b43e5feed7bdef22e9da0494cd941e2e9f96b698a75b21b03b1",
        "employee-egress-v2-20260814-candidate-02.authorization.json":
            "6fe6489fb5d32481909b88b860325dbbc35dec0c242d86f106327222e790c971",
        "employee-egress-v2-20260814-candidate-02.lifecycle.jsonl":
            "15982e15d454795d7052215ad46221b6f85cc26726ca0267a597f6d6002ec679",
        "employee-egress-v2-20260814-candidate-02.result.json":
            "dd8a5bac1586da4e44cc6a583c07289a91012bc34892f848ffb4a0241ae7561d",
    }
    evidence_directory = Path(__file__).parent / "evidence"
    for name, digest in expected.items():
        assert hashlib.sha256((evidence_directory / name).read_bytes()).hexdigest() == digest
        assert digest in launcher
    assert "$runStatus = 'retired_failed_inconclusive'" in launcher
    assert "employee.egress_input_qualify_run_retired" in launcher
    assert launcher.count("Remove-Item Env:\\LLM_API_KEY -ErrorAction SilentlyContinue") == 1
    assert "GetEnvironmentVariable('LLM_API_KEY'" not in launcher
    assert "Remove-TemporaryArtifacts" in launcher
