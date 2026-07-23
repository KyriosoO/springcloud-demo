import base64

import pytest

from agent_service.config.models import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        AGENT_SERVICE_JWT_HMAC_KEY_ACTIVE=base64.b64encode(b"A" * 32).decode(),
        AGENT_SERVICE_JWT_HMAC_KEY_PREVIOUS=base64.b64encode(b"B" * 32).decode(),
        employee_query_enabled=True,
    )
