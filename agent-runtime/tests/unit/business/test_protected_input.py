from __future__ import annotations

import pytest

from agent_runtime.business.protected_input import CompositeBusinessProtectedValueExtractor
from agent_runtime.business.query_plan import InvalidProtectedValue, ProtectedValueSlots


class _Extractor:
    def __init__(self, values: dict[str, object], *, request_id: str | None = None) -> None:
        self._values = values
        self._request_id = request_id

    def extract(self, question: str, *, request_id: str) -> ProtectedValueSlots:
        del question
        return ProtectedValueSlots(
            request_id=self._request_id or request_id,
            values=self._values,
        )


def test_composite_extractor_returns_one_domain_slots_without_selecting_domain() -> None:
    extractor = CompositeBusinessProtectedValueExtractor(
        (_Extractor({}), _Extractor({"slot-1": "protected"}))
    )

    slots = extractor.extract("employee query", request_id="request-1")

    assert slots.request_id == "request-1"
    assert dict(slots.values) == {"slot-1": "protected"}


def test_composite_extractor_returns_request_bound_empty_slots() -> None:
    extractor = CompositeBusinessProtectedValueExtractor((_Extractor({}), _Extractor({})))

    slots = extractor.extract("business query", request_id="request-1")

    assert slots.request_id == "request-1"
    assert dict(slots.values) == {}


@pytest.mark.parametrize(
    "extractors",
    (
        (_Extractor({"slot-1": "a"}), _Extractor({"slot-1": "b"})),
        (_Extractor({}, request_id="request-2"),),
    ),
)
def test_composite_extractor_fails_closed_for_ambiguous_or_cross_request_slots(
    extractors: tuple[_Extractor, ...],
) -> None:
    extractor = CompositeBusinessProtectedValueExtractor(extractors)

    with pytest.raises(InvalidProtectedValue):
        extractor.extract("business query", request_id="request-1")


def test_composite_extractor_rejects_empty_or_duplicate_registration() -> None:
    with pytest.raises(ValueError, match="business.invalid_protected_value_extractors"):
        CompositeBusinessProtectedValueExtractor(())
    duplicate = _Extractor({})
    with pytest.raises(ValueError, match="business.invalid_protected_value_extractors"):
        CompositeBusinessProtectedValueExtractor((duplicate, duplicate))
