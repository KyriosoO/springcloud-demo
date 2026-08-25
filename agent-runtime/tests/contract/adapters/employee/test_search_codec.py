from __future__ import annotations

import json
from typing import cast

import pytest

from agent_runtime.adapters.employee.codec import (
    EmployeeSearchArgumentValidator,
    EmployeeSearchRequestMapper,
    EmployeeSearchWireCodec,
)
from agent_runtime.adapters.employee.contracts import EmployeeSearchWireRequest
from agent_runtime.adapters.employee.normalizer import EmployeeSearchResponseNormalizer
from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessFailureResult,
    BusinessNoResult,
    BusinessRecordsResult,
    InvalidBusinessWireResponse,
)
from agent_runtime.business.settings import BusinessQueryConfigurationLoader


def _request() -> EmployeeSearchWireRequest:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)["employee.search"]
    validated = EmployeeSearchArgumentValidator().validate(
        {
            "filters": (
                {"field": "contact_address", "operator": "contains", "value": "上海"},
            ),
            "page": 1,
            "size": 20,
            "sorts": (),
        }
    )
    return EmployeeSearchRequestMapper().map(validated, settings)


def _payload(*, total: int = 1, relation: str = "eq") -> dict[str, object]:
    return {
        "took": 1,
        "hits": {
            "total": {"value": total, "relation": relation},
            "max_score": 1.0,
            "hits": [{
                "_index": "hidden-index",
                "_id": "hidden-id",
                "_score": 1.0,
                "_source": {
                    "idCardNo": "ABCDE12345",
                    "chineseName": "测试员工",
                    "contactAddress": "上海市测试街道",
                    "memberNo": "MEM001",
                    "phoneNo": "13800000000",
                    "email": "test@example.invalid",
                    "position": "工程师",
                    "workBaseSi": "never forwarded",
                    "workBaseAf": "never forwarded",
                    "embedding": [1.0, 2.0],
                    "unknownPrivate": "never forwarded",
                },
            }],
        },
    }


def _response(payload: object, *, content_type: str = "application/json") -> BoundedBusinessHttpResponse:
    return BoundedBusinessHttpResponse(
        status_code=200,
        content_type=content_type,
        body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )


def test_employee_search_encodes_only_existing_search_endpoint_and_dto() -> None:
    request = _request()
    outbound = EmployeeSearchWireCodec().encode(request)
    assert outbound.method == "POST"
    assert outbound.relative_path == "/employees/es/search"
    assert outbound.json_body is not None
    assert json.loads(outbound.json_body.content) == {
        "filters": [{"field": "contactAddress", "operator": "contains", "value": "上海"}],
        "from": 0,
        "size": 20,
        "sorts": [],
    }


@pytest.mark.parametrize(
    "content_type", ("application/json", "application/problem+json", "text/plain;charset=UTF-8")
)
def test_employee_search_strictly_projects_only_configured_source_fields(content_type: str) -> None:
    decoded = EmployeeSearchWireCodec().decode_success(
        request=_request(), response=_response(_payload(), content_type=content_type)
    )
    assert decoded.total == 1
    assert decoded.total_exact
    assert decoded.rows[0].contact_address == "上海市测试街道"
    assert not hasattr(decoded.rows[0], "work_base_si")
    assert not hasattr(decoded.rows[0], "work_base_af")
    assert not hasattr(decoded.rows[0], "embedding")
    result = EmployeeSearchResponseNormalizer().normalize_success(decoded)
    assert isinstance(result, BusinessRecordsResult)
    assert result.coverage.returned_count == 1


def test_employee_search_maps_gte_total_without_exposing_inexact_count() -> None:
    decoded = EmployeeSearchWireCodec().decode_success(
        request=_request(), response=_response(_payload(total=100, relation="gte"))
    )
    result = EmployeeSearchResponseNormalizer().normalize_success(decoded)
    assert isinstance(result, BusinessRecordsResult)
    assert result.coverage.truncated
    assert result.coverage.total_count is None


def test_employee_search_rejects_unprovable_total_and_missing_required_source() -> None:
    codec = EmployeeSearchWireCodec()
    for payload in (
        {"hits": {"total": 1, "hits": []}},
        {"hits": {"total": {"value": 1, "relation": "unknown"}, "hits": []}},
        {"hits": {"total": {"value": 1, "relation": "eq"}, "hits": [{"_source": {}}]}},
    ):
        with pytest.raises(InvalidBusinessWireResponse):
            codec.decode_success(request=_request(), response=_response(payload))


@pytest.mark.parametrize(
    "missing_field,missing_value",
    (
        ("chineseName", None),
        ("chineseName", ""),
        ("chineseName", "   "),
        ("idCardNo", None),
    ),
)
def test_employee_search_isolates_only_records_missing_required_identity(
    missing_field: str,
    missing_value: str | None,
) -> None:
    payload = _payload(total=2)
    hits = cast(dict[str, object], payload["hits"])
    rows = cast(list[dict[str, object]], hits["hits"])
    invalid_source: dict[str, object] = {
        "idCardNo": "ABCDE67890",
        "chineseName": "历史员工",
    }
    if missing_value is None:
        invalid_source.pop(missing_field)
    else:
        invalid_source[missing_field] = missing_value
    rows.append({"_source": invalid_source})

    decoded = EmployeeSearchWireCodec().decode_success(
        request=_request(), response=_response(payload)
    )
    result = EmployeeSearchResponseNormalizer().normalize_success(decoded)

    assert decoded.upstream_hit_count == 2
    assert not decoded.allow_partial_page
    assert len(decoded.rows) == 1
    assert isinstance(result, BusinessRecordsResult)
    assert result.coverage.returned_count == 1
    assert result.coverage.total_count == 2
    assert result.coverage.truncated


@pytest.mark.parametrize(
    "source",
    (
        {"idCardNo": 12345, "chineseName": "测试员工"},
        {"idCardNo": "ABCDE12345", "chineseName": "坏\x00值"},
        {"idCardNo": "ABCDE12345", "chineseName": "\n"},
        {"idCardNo": "ABCDE12345", "chineseName": "测试员工", "memberNo": 1},
        {"idCardNo": "ABCDE12345", "chineseName": None, "memberNo": 1},
    ),
)
def test_employee_search_does_not_isolate_invalid_types_controls_or_optional_fields(
    source: dict[str, object],
) -> None:
    payload = _payload(total=2)
    hits = cast(dict[str, object], payload["hits"])
    rows = cast(list[dict[str, object]], hits["hits"])
    rows.append({"_source": source})

    with pytest.raises(InvalidBusinessWireResponse, match="business.invalid_response"):
        EmployeeSearchWireCodec().decode_success(
            request=_request(), response=_response(payload)
        )


def test_employee_search_rejects_duplicate_key_invalid_media_and_oversized_payload() -> None:
    codec = EmployeeSearchWireCodec()
    invalid = (
        BoundedBusinessHttpResponse(
            status_code=200,
            content_type="application/json",
            body=b'{"hits":{"total":{"value":0,"value":0,"relation":"eq"},"hits":[]}}',
        ),
        BoundedBusinessHttpResponse(status_code=200, content_type="text/html", body=b"{}"),
        BoundedBusinessHttpResponse(
            status_code=200, content_type="text/plain;charset=ISO-8859-1", body=b"{}"
        ),
        BoundedBusinessHttpResponse(
            status_code=200, content_type="application/json", body=b" " * 1048577
        ),
        BoundedBusinessHttpResponse(
            status_code=200,
            content_type="application/json",
            body=b'{"hits":{"total":{"value":NaN,"relation":"eq"},"hits":[]}}',
        ),
    )
    for response in invalid:
        with pytest.raises(InvalidBusinessWireResponse):
            codec.decode_success(request=_request(), response=response)


def test_employee_search_normalizes_no_result_and_rejects_inconsistent_total() -> None:
    codec = EmployeeSearchWireCodec()
    no_result = codec.decode_success(
        request=_request(),
        response=_response({"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}),
    )
    assert isinstance(EmployeeSearchResponseNormalizer().normalize_success(no_result), BusinessNoResult)

    inconsistent = codec.decode_success(request=_request(), response=_response(_payload(total=2)))
    assert isinstance(
        EmployeeSearchResponseNormalizer().normalize_success(inconsistent), BusinessFailureResult
    )
