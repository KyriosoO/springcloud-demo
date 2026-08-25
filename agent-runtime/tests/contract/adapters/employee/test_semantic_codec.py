from __future__ import annotations

import json

import pytest

from agent_runtime.adapters.employee.codec import (
    EmployeeSemanticSearchArgumentValidator,
    EmployeeSemanticSearchRequestMapper,
    EmployeeSemanticSearchWireCodec,
)
from agent_runtime.business.contracts import BoundedBusinessHttpResponse, InvalidBusinessWireResponse
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
