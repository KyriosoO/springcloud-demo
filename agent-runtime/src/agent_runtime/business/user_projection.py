from __future__ import annotations

from typing import Any

from agent_runtime.capability_api.contracts import canonical_json_bytes
from agent_runtime.business.contracts import (
    BusinessActionDefinition,
    BusinessActionSettings,
    BusinessProjectionError,
    BusinessRecordsResult,
    BusinessUserField,
    BusinessUserRecord,
    BusinessUserResult,
)
from agent_runtime.business.transforms import BusinessTransformRegistry


class BusinessUserResultProjector:
    def __init__(self, transforms: BusinessTransformRegistry | None = None) -> None:
        self._transforms = transforms or BusinessTransformRegistry()

    def project(
        self,
        *,
        definition: BusinessActionDefinition[Any, Any, Any, Any],
        settings: BusinessActionSettings,
        result: BusinessRecordsResult[Any],
        max_user_result_bytes: int,
    ) -> BusinessUserResult:
        coverage = result.coverage
        if (
            not result.records
            or type(coverage.returned_count) is not int
            or coverage.returned_count != len(result.records)
            or type(coverage.truncated) is not bool
            or (
                coverage.total_count is not None
                and (type(coverage.total_count) is not int or coverage.total_count < coverage.returned_count)
            )
            or type(max_user_result_bytes) is not int
            or max_user_result_bytes <= 0
        ):
            raise BusinessProjectionError("business.minimum_user_result_not_met")
        selections = {item.field_id: item.transform_id for item in settings.user_transforms}
        allowed = set(settings.user_result_field_ids)
        definitions = {item.field_id: item for item in definition.field_definitions}
        records: list[BusinessUserRecord] = []
        for index, record in enumerate(result.records, 1):
            fields: list[BusinessUserField] = []
            for field_definition in definition.field_definitions:
                if field_definition.field_id not in allowed or not field_definition.user_visible_by_code:
                    continue
                value = field_definition.extractor(record)
                if value is None:
                    continue
                transform = selections.get(field_definition.field_id)
                if transform is None:
                    raise BusinessProjectionError("business.minimum_user_result_not_met")
                fields.append(
                    BusinessUserField(
                        field_id=field_definition.field_id,
                        value=self._transforms.apply(transform_id=transform, definition=field_definition, value=value),
                    )
                )
            present = {item.field_id for item in fields}
            if not set(definition.required_user_field_ids).issubset(present):
                raise BusinessProjectionError("business.minimum_user_result_not_met")
            records.append(BusinessUserRecord(record_ref=f"record-{index:04d}", fields=tuple(fields)))
        user_result = BusinessUserResult(
            capability_id=definition.descriptor.capability_id,
            records=tuple(records),
            coverage=coverage,
        )
        if len(canonical_json_bytes(user_result.to_domain_result())) > max_user_result_bytes:
            raise BusinessProjectionError("business.user_result_too_large")
        return user_result
