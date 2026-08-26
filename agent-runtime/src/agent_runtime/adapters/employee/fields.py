from __future__ import annotations

from typing import Any, Callable

from agent_runtime.business.contracts import (
    BusinessFieldDefinition,
    BusinessFieldTransform,
    BusinessFieldValueType,
    DataClass,
)
from agent_runtime.adapters.employee.contracts import EmployeeDetailRecord, EmployeeSearchRecord
from agent_runtime.business.contracts import business_query_v2_result_contracts


def employee_field_definitions() -> tuple[BusinessFieldDefinition[EmployeeDetailRecord, Any], ...]:
    bounded = frozenset({BusinessFieldTransform.BOUNDED_TEXT})
    masked = frozenset({BusinessFieldTransform.MASK_KEEP_LAST4})
    return (
        BusinessFieldDefinition(field_id="employee_id_masked", value_type=BusinessFieldValueType.IDENTIFIER, data_class=DataClass.PERSONAL_IDENTIFIER, extractor=lambda r: r.id_card_no, user_visible_by_code=True, model_candidate_by_code=False, allowed_user_transforms=masked, allowed_model_transforms=frozenset()),
        BusinessFieldDefinition(field_id="member_no_masked", value_type=BusinessFieldValueType.IDENTIFIER, data_class=DataClass.EMPLOYEE_IDENTIFIER, extractor=lambda r: r.member_no, user_visible_by_code=True, model_candidate_by_code=False, allowed_user_transforms=masked, allowed_model_transforms=frozenset()),
        BusinessFieldDefinition(field_id="chinese_name", value_type=BusinessFieldValueType.TEXT, data_class=DataClass.PERSONAL_IDENTIFIER, extractor=lambda r: r.chinese_name, user_visible_by_code=True, model_candidate_by_code=False, allowed_user_transforms=bounded, allowed_model_transforms=frozenset()),
        BusinessFieldDefinition(field_id="public_email", value_type=BusinessFieldValueType.TEXT, data_class=DataClass.CONTACT, extractor=lambda r: r.public_email, user_visible_by_code=True, model_candidate_by_code=False, allowed_user_transforms=bounded, allowed_model_transforms=frozenset()),
        BusinessFieldDefinition(field_id="position", value_type=BusinessFieldValueType.TEXT, data_class=DataClass.BUSINESS_INTERNAL, extractor=lambda r: r.position, user_visible_by_code=True, model_candidate_by_code=True, allowed_user_transforms=bounded, allowed_model_transforms=bounded),
    )


def employee_search_field_definitions() -> tuple[
    BusinessFieldDefinition[EmployeeSearchRecord, Any], ...
]:
    definitions: list[BusinessFieldDefinition[EmployeeSearchRecord, Any]] = []
    for contract in business_query_v2_result_contracts("employee.search"):
        field_id = contract.field_id
        model_transforms = (
            frozenset({contract.model_transform})
            if contract.model_transform is not None
            else frozenset()
        )
        definitions.append(
            BusinessFieldDefinition(
                field_id=field_id,
                value_type=contract.value_type,
                data_class=contract.data_class,
                extractor=_employee_search_extractor(field_id),
                user_visible_by_code=True,
                model_candidate_by_code=contract.model_transform is not None,
                allowed_user_transforms=frozenset({contract.user_transform}),
                allowed_model_transforms=model_transforms,
            )
        )
    return tuple(definitions)


def _employee_search_extractor(field_id: str) -> Callable[[EmployeeSearchRecord], Any]:
    def extract(record: EmployeeSearchRecord) -> Any:
        return getattr(record, field_id)

    return extract
