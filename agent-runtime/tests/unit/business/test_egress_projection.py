from __future__ import annotations

from collections.abc import Mapping

from agent_runtime.adapters.transaction.definition import transaction_search_definition
from agent_runtime.adapters.transaction.settings import TransactionAdapterSettings
from agent_runtime.business.contracts import (
    BusinessResultCoverage,
    BusinessUserField,
    BusinessUserRecord,
    BusinessUserResult,
)
from agent_runtime.business.egress import BusinessEgressProjector
from agent_runtime.business.settings import BusinessGlobalSettings, GlobalBusinessEgressPolicy
from agent_runtime.capability_api.contracts import EgressDisposition, JsonObject, JsonValue


def _json_object(value: JsonValue) -> JsonObject:
    assert isinstance(value, Mapping)
    return value


def _json_array(value: JsonValue) -> tuple[JsonValue, ...]:
    assert isinstance(value, tuple)
    return value


def _user_result(transaction_type: str = "PAY") -> BusinessUserResult:
    return BusinessUserResult(
        capability_id="transaction.search",
        records=(BusinessUserRecord(
            record_ref="record-0001",
            fields=(
                BusinessUserField(field_id="transaction_type", value=transaction_type),
                BusinessUserField(field_id="amount", value="1.24"),
            ),
        ),),
        coverage=BusinessResultCoverage(returned_count=1, truncated=False, total_count=1),
    )


def test_egress_projection_builds_only_configured_transformed_facts() -> None:
    settings = TransactionAdapterSettings.from_env({
        "AGENT_TRANSACTION_SEARCH_MODEL_FIELDS": "transaction_type,amount",
    }).action
    result = BusinessEgressProjector().project(
        definition=transaction_search_definition(),
        settings=settings,
        user_result=_user_result(),
        policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings(egress_enabled=True)),
        config_snapshot_id="a" * 64,
    )

    assert result.disposition is EgressDisposition.ALLOWED
    assert result.safe_payload is not None
    facts = tuple(_json_object(item) for item in _json_array(result.safe_payload["facts"]))
    assert tuple(_json_object(item["source"])["field_id"] for item in facts) == (
        "transaction_type",
        "amount",
    )
    assert tuple(item["value"] for item in facts) == ("PAY", "1.24")


def test_egress_projection_fails_closed_when_global_text_limit_is_exceeded() -> None:
    settings = TransactionAdapterSettings.from_env({
        "AGENT_TRANSACTION_SEARCH_MODEL_FIELDS": "transaction_type",
    }).action
    result = BusinessEgressProjector().project(
        definition=transaction_search_definition(),
        settings=settings,
        user_result=_user_result("X" * 33),
        policy=GlobalBusinessEgressPolicy.from_settings(BusinessGlobalSettings(
            egress_enabled=True,
            max_text_value_chars=32,
        )),
        config_snapshot_id="a" * 64,
    )

    assert result.disposition is EgressDisposition.DENIED
    assert result.reason_code == "business.payload_limit"
