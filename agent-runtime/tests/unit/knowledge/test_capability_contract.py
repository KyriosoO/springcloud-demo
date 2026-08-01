from __future__ import annotations

import pytest

from agent_runtime.knowledge.capability import KnowledgeArgumentValidator
from agent_runtime.knowledge.provider import KnowledgeCapabilityProvider
from agent_runtime.capability_api.contracts import InvalidCapabilityArguments


def test_descriptor_and_empty_argument_contract_are_exact() -> None:
    registration = KnowledgeCapabilityProvider(enabled=False, handler=None).registrations()[0]

    assert registration.descriptor.capability_id == "knowledge.query"
    assert registration.descriptor.api_version == 1
    assert registration.descriptor.argument_schema == {
        "type": "object", "properties": {}, "required": (), "additionalProperties": False
    }
    assert KnowledgeArgumentValidator().validate({}) is not None
    with pytest.raises(InvalidCapabilityArguments, match="knowledge.arguments_not_empty"):
        KnowledgeArgumentValidator().validate({"domain": "tax.policy"})

