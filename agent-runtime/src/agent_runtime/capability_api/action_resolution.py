from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from agent_runtime.capability_api.contracts import JsonObject, freeze_json_object


class LocalActionInvalidReason(StrEnum):
    MISSING_REQUIRED = "missing_required"
    DUPLICATE_ARGUMENT = "duplicate_argument"
    CONFLICTING_ARGUMENT = "conflicting_argument"
    UNSUPPORTED_CLAUSE = "unsupported_clause"
    MALFORMED_VALUE = "malformed_value"
    AMBIGUOUS_INTENT = "ambiguous_intent"


class LocalActionResolutionKind(StrEnum):
    NO_MATCH = "no_match"
    CANDIDATE = "candidate"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalActionResolution:
    kind: LocalActionResolutionKind
    arguments: JsonObject | None = None
    reason: LocalActionInvalidReason | None = None

    def __post_init__(self) -> None:
        if self.kind is LocalActionResolutionKind.CANDIDATE and self.arguments is not None and self.reason is None:
            try:
                arguments = freeze_json_object(
                    self.arguments,
                    max_bytes=65536,
                    max_depth=16,
                    max_collection_items=2048,
                )
            except Exception:
                arguments = None
            if arguments is None:
                raise ValueError("core.invalid_local_action_resolution") from None
            object.__setattr__(self, "arguments", arguments)
            return
        if self.kind is LocalActionResolutionKind.INVALID and self.arguments is None and isinstance(
            self.reason,
            LocalActionInvalidReason,
        ):
            return
        if self.kind is LocalActionResolutionKind.NO_MATCH and self.arguments is None and self.reason is None:
            return
        raise ValueError("core.invalid_local_action_resolution")


@runtime_checkable
class LocalActionResolver(Protocol):
    @property
    def capability_id(self) -> str: ...

    def resolve(self, question: str) -> LocalActionResolution: ...
