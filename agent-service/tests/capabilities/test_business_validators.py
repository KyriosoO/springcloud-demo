from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from agent_service.api.errors import AgentFailure
from agent_service.capabilities.business.validators import validate_employee_query_payload
from agent_service.security.models import PlanningAuthorization, SubjectRef


def _authorization() -> PlanningAuthorization:
    return PlanningAuthorization(
        subject=SubjectRef(type="USER", id="dylan"),
        tenantRef="tenant-main",
        capabilities={"QUERY"},
        domains={"EMPLOYEE"},
        filterFields={"EMPLOYEE": {"position", "workBaseSi"}},
        displayFields={"EMPLOYEE": {"position", "workBaseSi"}},
        sortFields={"EMPLOYEE": {"position"}},
        operators={"EMPLOYEE.POSITION": {"EQ", "IN"}},
        identityEvidenceVersion="identity-1",
        authEvidenceVersion="auth-1",
        policyVersion="policy-1",
        validUntil=datetime.now(UTC) + timedelta(minutes=1),
    )


def test_valid_employee_query_is_canonicalized():
    request = validate_employee_query_payload(
        {
            "filters": [{"field": "position", "operator": "EQ", "values": ["Engineer"]}],
            "select": ["position"],
            "sorts": [{"field": "position", "direction": "ASC"}],
            "page": {"number": 0, "size": 20},
        },
        _authorization(),
        uuid4(),
        datetime.now(UTC) + timedelta(seconds=10),
    )
    assert request.filters[0].field == "position"


def test_unknown_field_stops_before_client():
    with pytest.raises(AgentFailure):
        validate_employee_query_payload(
            {
                "filters": [{"field": "salary", "operator": "EQ", "values": ["1"]}],
                "select": ["position"],
                "sorts": [],
                "page": {"number": 0, "size": 20},
            },
            _authorization(),
            uuid4(),
            datetime.now(UTC) + timedelta(seconds=10),
        )
