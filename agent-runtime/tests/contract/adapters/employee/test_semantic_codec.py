from __future__ import annotations

import json

import pytest

from agent_runtime.adapters.employee.codec import (
    EmployeeSemanticSearchArgumentValidator,
    EmployeeSemanticSearchRequestMapper,
    EmployeeSemanticSearchWireCodec,
)
from agent_runtime.adapters.employee.normalizer import EmployeeSearchResponseNormalizer
from agent_runtime.business.contracts import (
    BoundedBusinessHttpResponse,
    BusinessFailureResult,
    BusinessRecordsResult,
    InvalidBusinessWireResponse,
)
from agent_runtime.business.settings import BusinessQueryConfigurationLoader


def test_semantic_codec_uses_existing_vector_endpoint_and_no_user_vector_or_filter() -> None:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    selected = EmployeeSemanticSearchArgumentValidator().validate(
        {"query": "擅长分布式架构", "size": 5}
    )
    request = EmployeeSemanticSearchRequestMapper().map(selected, settings)
    outbound = EmployeeSemanticSearchWireCodec().encode(request)
    assert outbound.method == "POST"
    assert outbound.relative_path == "/employees/es/vector-search"
    assert outbound.json_body is not None
    assert json.loads(outbound.json_body.content) == {
        "queryText": "擅长分布式架构",
        "k": 5,
        "embeddingField": "embedding",
        "embeddingDims": 1024,
        "numCandidates": 100,
        "trackTotalHits": 10000,
    }
    assert b"queryVector" not in outbound.json_body.content
    assert b"filters" not in outbound.json_body.content


def test_semantic_codec_reuses_same_bounded_strict_employee_hits_decoder() -> None:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    request = EmployeeSemanticSearchRequestMapper().map(
        EmployeeSemanticSearchArgumentValidator().validate({"query": "架构师", "size": 1}),
        settings,
    )
    codec = EmployeeSemanticSearchWireCodec()
    response = BoundedBusinessHttpResponse(
        status_code=200,
        content_type="text/plain;charset=UTF-8",
        body=json.dumps(
            {
                "hits": {
                    "total": {"value": 1, "relation": "eq"},
                    "hits": [{"_source": {
                        "idCardNo": "ABCDE12345",
                        "chineseName": "测试员工",
                        "position": "架构师",
                        "privateField": "must-not-project",
                    }}],
                }
            },
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    decoded = codec.decode_success(request=request, response=response)
    assert decoded.rows[0].position == "架构师"
    assert not hasattr(decoded.rows[0], "privateField")

    invalid = BoundedBusinessHttpResponse(
        status_code=200,
        content_type="application/json",
        body=b'{"hits":{"total":{"value":0,"relation":"invalid"},"hits":[]}}',
    )
    with pytest.raises(InvalidBusinessWireResponse):
        codec.decode_success(request=request, response=invalid)


def test_semantic_codec_preserves_real_partial_page_and_isolates_missing_name() -> None:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    request = EmployeeSemanticSearchRequestMapper().map(
        EmployeeSemanticSearchArgumentValidator().validate(
            {"query": "金融风控经验", "size": 20}
        ),
        settings,
    )
    hits = [
        {"_source": {"idCardNo": f"ABCDE{index:05d}", "chineseName": f"员工{index}"}}
        for index in range(9)
    ]
    hits.append({"_source": {"idCardNo": "ABCDE99999"}})
    response = BoundedBusinessHttpResponse(
        status_code=200,
        content_type="text/plain;charset=UTF-8",
        body=json.dumps(
            {"hits": {"total": {"value": 20, "relation": "eq"}, "hits": hits}},
            ensure_ascii=False,
        ).encode("utf-8"),
    )

    decoded = EmployeeSemanticSearchWireCodec().decode_success(
        request=request, response=response
    )
    result = EmployeeSearchResponseNormalizer().normalize_success(decoded)

    assert decoded.upstream_hit_count == 10
    assert decoded.allow_partial_page
    assert len(decoded.rows) == 9
    assert isinstance(result, BusinessRecordsResult)
    assert result.coverage.returned_count == 9
    assert result.coverage.total_count == 20
    assert result.coverage.truncated


@pytest.mark.parametrize(
    "total,hits,codec_rejects",
    (
        (20, [], False),
        (1, [{"_source": {"idCardNo": "ABCDE12345"}}], True),
        (0, [{"_source": {"idCardNo": "ABCDE12345", "chineseName": "员工"}}], True),
    ),
)
def test_semantic_partial_page_still_rejects_inconsistent_or_unusable_hits(
    total: int,
    hits: list[dict[str, object]],
    codec_rejects: bool,
) -> None:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    request = EmployeeSemanticSearchRequestMapper().map(
        EmployeeSemanticSearchArgumentValidator().validate(
            {"query": "金融风控经验", "size": 20}
        ),
        settings,
    )
    response = BoundedBusinessHttpResponse(
        status_code=200,
        content_type="application/json",
        body=json.dumps(
            {"hits": {"total": {"value": total, "relation": "eq"}, "hits": hits}},
            ensure_ascii=False,
        ).encode("utf-8"),
    )
    if codec_rejects:
        with pytest.raises(InvalidBusinessWireResponse):
            EmployeeSemanticSearchWireCodec().decode_success(
                request=request, response=response
            )
        return

    decoded = EmployeeSemanticSearchWireCodec().decode_success(
        request=request, response=response
    )
    assert isinstance(
        EmployeeSearchResponseNormalizer().normalize_success(decoded),
        BusinessFailureResult,
    )
