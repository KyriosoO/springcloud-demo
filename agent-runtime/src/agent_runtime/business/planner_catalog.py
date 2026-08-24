from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from agent_runtime.capability_api.contracts import JsonObject, freeze_json_object
from agent_runtime.business.contracts import BusinessActionDefinition
from agent_runtime.business.settings import BusinessConfigurationSnapshot


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessPlannerCatalog:
    snapshot_id: str
    payload: JsonObject


def build_business_planner_catalog(
    definitions: Sequence[BusinessActionDefinition[Any, Any, Any, Any]],
    snapshot: BusinessConfigurationSnapshot,
) -> BusinessPlannerCatalog:
    by_action = {item.descriptor.capability_id: item for item in definitions}
    if not definitions or len(by_action) != len(tuple(definitions)):
        raise ValueError("business.configuration_invalid")
    actions: list[dict[str, object]] = []
    for action_id, settings in snapshot.actions:
        if not settings.enabled:
            continue
        definition = by_action.get(action_id)
        if definition is None:
            raise ValueError("business.plan_snapshot_mismatch")
        query_by_name = {item.logical_name: item for item in definition.query_fields}
        fields: list[dict[str, object]] = []
        for configured in settings.query_fields:
            if not configured.enabled:
                continue
            code = query_by_name.get(configured.logical_name)
            if code is None:
                raise ValueError("business.plan_snapshot_mismatch")
            fields.append(
                {
                    "logical_name": code.logical_name,
                    "description": configured.model_safe_description,
                    "value_type": code.value_type.value,
                    "operators": tuple(item.value for item in configured.allowed_operators),
                    "input_exposure": code.input_exposure.value,
                    "required": configured.required,
                    "max_text_chars": configured.max_text_chars,
                }
            )
        if not fields:
            raise ValueError("business.plan_snapshot_mismatch")
        enabled_names = {item["logical_name"] for item in fields}
        rules = tuple(
            {
                "rule_id": rule.rule_id,
                "kind": rule.kind.value,
                "field_names": tuple(
                    name for name in rule.field_names if name in enabled_names
                ),
            }
            for rule in definition.combination_rules
            if rule.rule_id in settings.combination_rule_ids
        )
        actions.append(
            {
                "domain": str(definition.domain_id),
                "action": action_id,
                "fields": tuple(fields),
                "combination_rules": rules,
                "limits": {
                    "max_decimal_abs": settings.max_decimal_abs,
                    "max_decimal_scale": settings.max_decimal_scale,
                    "fixed_page": settings.fixed_page,
                    "max_page_size": settings.max_page_size,
                    "allowed_sort_fields": settings.allowed_sort_field_ids,
                    "allowed_sort_directions": settings.allowed_sort_directions,
                    "max_sort_items": settings.max_sort_items,
                },
            }
        )
    payload = freeze_json_object(
        {
            "schema_version": 1,
            "snapshot_id": snapshot.snapshot_id,
            "actions": tuple(actions),
            "unsupported": {
                "domain": "unsupported",
                "action": "unsupported",
                "arguments": {},
            },
        },
        max_bytes=32768,
        max_depth=8,
        max_collection_items=256,
    )
    return BusinessPlannerCatalog(snapshot_id=snapshot.snapshot_id, payload=payload)
