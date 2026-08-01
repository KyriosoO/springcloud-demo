from __future__ import annotations

import re
from types import MappingProxyType
from typing import Mapping

from agent_runtime.model.contracts import AnswerGroundingPolicy, MissingGroundingPolicy


_CAPABILITY_ID = re.compile(r"[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+")


class GroundingPolicyRegistry:
    __slots__ = ("_policies",)

    def __init__(self, policies: Mapping[str, AnswerGroundingPolicy]) -> None:
        frozen: dict[str, AnswerGroundingPolicy] = {}
        for capability_id, policy in policies.items():
            if not isinstance(capability_id, str) or not _CAPABILITY_ID.fullmatch(capability_id):
                raise ValueError("model.invalid_grounding_policy")
            if capability_id in frozen or not callable(getattr(policy, "validate", None)):
                raise ValueError("model.invalid_grounding_policy")
            frozen[capability_id] = policy
        self._policies = MappingProxyType(frozen)

    def require(self, capability_id: str) -> AnswerGroundingPolicy:
        if not isinstance(capability_id, str) or not _CAPABILITY_ID.fullmatch(capability_id):
            raise MissingGroundingPolicy("model.missing_grounding_policy")
        policy = self._policies.get(capability_id)
        if policy is None:
            raise MissingGroundingPolicy("model.missing_grounding_policy")
        return policy

