from __future__ import annotations

from dataclasses import replace

import pytest

from agent_runtime.adapters.employee.codec import (
    EmployeeSemanticSearchArgumentValidator,
    EmployeeSemanticSearchRequestMapper,
)
from agent_runtime.adapters.employee.definition import employee_semantic_search_definition
from agent_runtime.adapters.employee.provider import EmployeeSearchDomainProvider
from agent_runtime.business.contracts import (
    BusinessAnswerMode,
    BusinessServiceKey,
    InvalidBusinessArguments,
)
from agent_runtime.business.provider import BusinessSupportFactory
from agent_runtime.business.settings import (
    BusinessConfigurationSource,
    BusinessGlobalSettings,
    BusinessQueryConfigurationLoader,
    BusinessServiceBinding,
)
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments, JsonValue


def test_semantic_definition_exposes_only_query_and_size() -> None:
    definition = employee_semantic_search_definition()
    assert definition.descriptor.capability_id == "employee.semantic_search"
    assert set(definition.descriptor.argument_schema["properties"]) == {"query", "size"}  # type: ignore[arg-type]
    assert definition.filter_field_ids_by_code == frozenset()
    assert definition.sort_field_ids_by_code == frozenset()
    assert definition.answer_mode is BusinessAnswerMode.STRUCTURED_ONLY
    assert definition.local_action_resolver is None
    assert definition.contract_limits.max_timeout_ms == 10000


def test_semantic_mapper_uses_only_fixed_code_bound_vector_profile() -> None:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    assert settings.timeout_ms == 10000
    selected = EmployeeSemanticSearchArgumentValidator().validate(
        {"query": "熟悉分布式系统的开发工程师", "size": 10}
    )
    wire = EmployeeSemanticSearchRequestMapper().map(selected, settings)
    assert wire.query == "熟悉分布式系统的开发工程师"
    assert wire.size == 10
    assert wire.embedding_field == "embedding"
    assert wire.embedding_dims == 1024
    assert wire.num_candidates == 100
    assert wire.track_total_hits == 10000


@pytest.mark.parametrize(
    "arguments",
    (
        {"query": "工程师", "size": 10, "filters": ()},
        {"query": "工程师", "size": 10, "queryVector": (1, 2)},
        {"query": "工程师", "size": 10, "embeddingField": "another"},
        {"query": "工程师", "size": 0},
        {"query": "工程师", "size": 51},
        {"query": "联系电话 13800000000", "size": 10},
        {"query": "test@example.invalid", "size": 10},
        {"query": "11010519491231002X", "size": 10},
        {"query": "工程师\x00", "size": 10},
    ),
)
def test_semantic_validator_rejects_sensitive_values_vectors_filters_and_bounds(
    arguments: dict[str, JsonValue],
) -> None:
    with pytest.raises(InvalidCapabilityArguments):
        EmployeeSemanticSearchArgumentValidator().validate(arguments)


def test_semantic_mapper_rejects_profile_or_filter_configuration_mismatch() -> None:
    settings = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)[
        "employee.semantic_search"
    ]
    selected = EmployeeSemanticSearchArgumentValidator().validate(
        {"query": "工程师", "size": 10}
    )
    for invalid in (
        replace(settings, semantic_profile_id="unknown"),
        replace(settings, allowed_filter_field_ids=("contact_address",)),
        replace(settings, fixed_page=None),
        replace(settings, max_page_size=5),
    ):
        with pytest.raises(InvalidBusinessArguments):
            EmployeeSemanticSearchRequestMapper().map(selected, invalid)


def test_employee_provider_contains_two_distinct_actions_and_no_detail_fallback() -> None:
    actions = dict(BusinessQueryConfigurationLoader.load_v2_resource().actions)
    provider = EmployeeSearchDomainProvider(
        search_settings=actions["employee.search"],
        semantic_settings=actions["employee.semantic_search"],
        service_binding=BusinessServiceBinding(
            service_key=BusinessServiceKey("employee-service"),
            base_endpoint="http://127.0.0.1:9210",
        ),
    )
    fragment = provider.configuration_fragment()
    snapshot = BusinessSupportFactory().build(
        definitions=provider.definitions(),
        config=BusinessConfigurationSource(
            global_settings=BusinessGlobalSettings(),
            actions=fragment.actions,
            service_bindings=fragment.service_bindings,
        ),
        core_max_domain_result_bytes=262144,
    )
    assert {item.definition.descriptor.capability_id for item in snapshot.actions} == {
        "employee.search", "employee.semantic_search"
    }
