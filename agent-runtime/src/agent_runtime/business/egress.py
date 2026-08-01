from __future__ import annotations

from typing import Any

from agent_runtime.capability_api.contracts import ContractViolation, EgressDisposition, ModelEgressResult, freeze_json_object
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessAnswerMode,
    BusinessProjectionError,
    BusinessUserResult,
)
from agent_runtime.business.settings import GlobalBusinessEgressPolicy
from agent_runtime.business.transforms import BusinessTransformRegistry


class BusinessEgressProjector:
    def __init__(self, transforms: BusinessTransformRegistry | None = None) -> None:
        self._transforms = transforms or BusinessTransformRegistry()

    def project(
        self,
        *,
        definition: BusinessActionDefinition[Any, Any, Any, Any],
        settings: BusinessActionSettings,
        user_result: BusinessUserResult,
        policy: GlobalBusinessEgressPolicy,
        config_snapshot_id: str,
    ) -> ModelEgressResult:
        if definition.answer_mode is BusinessAnswerMode.STRUCTURED_ONLY:
            return ModelEgressResult(disposition=EgressDisposition.NOT_APPLICABLE)
        if not policy.enabled:
            return self._denied("business.egress_disabled")
        if len(config_snapshot_id) != 64 or any(character not in "0123456789abcdef" for character in config_snapshot_id):
            return self._denied("business.policy_conflict")
        definitions = {item.field_id: item for item in definition.field_definitions}
        transforms = {item.field_id: item.transform_id for item in settings.model_transforms}
        user_transforms = {item.field_id: item.transform_id for item in settings.user_transforms}
        model_fields = set(settings.model_field_ids)
        facts: list[dict[str, object]] = []
        for record in user_result.records:
            if len(record.fields) > policy.max_fields_per_record:
                return self._denied("business.payload_limit")
            source_fields = {item.field_id: item.value for item in record.fields}
            for field_definition in definition.field_definitions:
                field_id = field_definition.field_id
                if field_id not in model_fields or field_id not in source_fields or not field_definition.model_candidate_by_code:
                    continue
                if field_definition.data_class in policy.always_denied_classes:
                    return self._denied("business.policy_conflict")
                transform = transforms.get(field_id)
                if transform is None:
                    return self._denied("business.policy_conflict")
                try:
                    if user_transforms.get(field_id) is transform:
                        value = source_fields[field_id]
                    else:
                        value = self._transforms.apply(
                            transform_id=transform,
                            definition=definitions[field_id],
                            value=source_fields[field_id],
                        )
                except BusinessProjectionError:
                    return self._denied("business.transform_failed")
                if type(value) is str and len(value) > policy.max_text_value_chars:
                    return self._denied("business.payload_limit")
                facts.append(
                    {
                        "fact_id": f"fact-{len(facts) + 1:04d}",
                        "value_type": field_definition.value_type.value,
                        "value": value,
                        "transform_id": transform.value,
                        "source": {"record_ref": record.record_ref, "field_id": field_id},
                    }
                )
                if len(facts) > policy.max_safe_facts:
                    return self._denied("business.payload_limit")
        if not facts:
            return self._denied("business.no_model_fields")
        try:
            payload = freeze_json_object(
                {
                    "schema_version": 1,
                    "policy_version": policy.policy_version,
                    "config_snapshot_id": config_snapshot_id,
                    "facts": tuple(facts),
                    "presentation": {"mode": "business_facts", "action_id": definition.descriptor.capability_id},
                    "coverage": {"truncated": user_result.coverage.truncated},
                },
                max_bytes=policy.max_safe_payload_bytes,
                max_depth=8,
                max_collection_items=256,
            )
        except ContractViolation:
            return self._denied("business.payload_limit")
        return ModelEgressResult(
            disposition=EgressDisposition.ALLOWED,
            policy_version=policy.policy_version,
            safe_payload=payload,
        )

    @staticmethod
    def _denied(reason: str) -> ModelEgressResult:
        return ModelEgressResult(
            disposition=EgressDisposition.DENIED,
            policy_version="business-egress-v1",
            reason_code=reason,
        )
