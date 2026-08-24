from __future__ import annotations

from typing import Protocol, Sequence

from agent_runtime.business.query_plan import InvalidProtectedValue, ProtectedValueSlots


class ProtectedValueExtractor(Protocol):
    def extract(self, question: str, *, request_id: str) -> ProtectedValueSlots: ...


class CompositeBusinessProtectedValueExtractor:
    """Combines value protection without selecting a Business domain or action."""

    __slots__ = ("_extractors",)

    def __init__(self, extractors: Sequence[ProtectedValueExtractor]) -> None:
        values = tuple(extractors)
        if not values or len({id(item) for item in values}) != len(values):
            raise ValueError("business.invalid_protected_value_extractors")
        self._extractors = values

    def extract(self, question: str, *, request_id: str) -> ProtectedValueSlots:
        selected: ProtectedValueSlots | None = None
        for extractor in self._extractors:
            slots = extractor.extract(question, request_id=request_id)
            if slots.request_id != request_id:
                raise InvalidProtectedValue()
            if not slots.values:
                continue
            if selected is not None:
                raise InvalidProtectedValue()
            selected = slots
        return selected or ProtectedValueSlots(request_id=request_id, values={})
