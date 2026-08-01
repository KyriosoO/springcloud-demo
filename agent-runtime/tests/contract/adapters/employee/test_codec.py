from __future__ import annotations

import json

import pytest

from agent_runtime.adapters.employee.codec import EmployeeDetailWireCodec
from agent_runtime.adapters.employee.contracts import EmployeeDetailWireRequest
from agent_runtime.business.contracts import BoundedBusinessHttpResponse, InvalidBusinessWireResponse


def _response(identifier: str = "ABCDE") -> BoundedBusinessHttpResponse:
    return BoundedBusinessHttpResponse(
        status_code=200,
        content_type="application/json",
        body=json.dumps({
            "idCardNo": identifier, "memberNo": "MEM01", "chineseName": "测试员工",
            "publicEmail": "test@example.invalid", "position": "工程师", "workBaseSi": "上海",
            "bankAccount": "must-not-project", "address": {"secret": "must-not-project"},
        }, ensure_ascii=False).encode(),
    )


def test_employee_codec_percent_encodes_once_and_projects_only_six_fields() -> None:
    codec = EmployeeDetailWireCodec()
    request = EmployeeDetailWireRequest(employee_identifier="员工ABCDE")
    encoded = codec.encode(request)
    assert encoded.method == "GET"
    assert encoded.relative_path.startswith("/employees/%E5%91%98%E5%B7%A5")
    assert encoded.query == () and encoded.json_body is None

    decoded = codec.decode_success(request=EmployeeDetailWireRequest(employee_identifier="ABCDE"), response=_response())
    assert decoded.position == "工程师"
    assert not hasattr(decoded, "bank_account")
    assert not hasattr(decoded, "address")


def test_employee_codec_rejects_identifier_mismatch_and_invalid_target_type() -> None:
    codec = EmployeeDetailWireCodec()
    with pytest.raises(InvalidBusinessWireResponse):
        codec.decode_success(request=EmployeeDetailWireRequest(employee_identifier="OTHER"), response=_response())
    raw = json.loads(_response().body or b"{}")
    raw["position"] = {"unexpected": True}
    with pytest.raises(InvalidBusinessWireResponse):
        codec.decode_success(
            request=EmployeeDetailWireRequest(employee_identifier="ABCDE"),
            response=BoundedBusinessHttpResponse(status_code=200, content_type="application/json", body=json.dumps(raw, ensure_ascii=False).encode()),
        )
    with pytest.raises(InvalidBusinessWireResponse):
        codec.decode_success(
            request=EmployeeDetailWireRequest(employee_identifier="ABCDE"),
            response=BoundedBusinessHttpResponse(
                status_code=200,
                content_type="application/json",
                body=(
                    b'{"idCardNo":"ABCDE","memberNo":"MEM01","chineseName":"name",'
                    b'"publicEmail":null,"position":null,"workBaseSi":null,"unknown":NaN}'
                ),
            ),
        )
