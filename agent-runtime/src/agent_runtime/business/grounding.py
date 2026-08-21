from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping

from agent_runtime.model.contracts import (
    GroundingDecision,
    GroundingInput,
    GroundingRejectionReason,
)

_MARKER = re.compile(r"\[(fact-[0-9]{4})\]")
_SPLIT = re.compile(r"(?<=[?!。！？;；\n])|(?<=\.)(?![0-9])")
_FACT_ID = re.compile(r"fact-[0-9]{4}")
_RECORD_REF = re.compile(r"record-[0-9]{4}")
_FIELD_ID = re.compile(r"[a-z][a-z0-9_]{0,127}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_DATE = re.compile(r"(?<![0-9])(?:[0-9]{4}-[0-9]{2}-[0-9]{2})(?![0-9])")
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.:%+-])[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?%?(?![A-Za-z0-9_.:%+-])")
_ASCII = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:%+-]{0,127}")
_VALUE_TYPES = {"boolean", "integer", "decimal", "date", "datetime", "enum", "text", "identifier"}
_TRANSFORMS = {"identity_scalar", "bounded_text", "mask_keep_last4", "date_only", "decimal_2", "enum_code"}


def _overlaps(span: tuple[int, int], occupied: list[tuple[int, int]]) -> bool:
    return any(span[0] < current[1] and current[0] < span[1] for current in occupied)


def _masked_tokens(text: str) -> tuple[tuple[str, tuple[int, int]], ...]:
    found: list[tuple[str, tuple[int, int]]] = []
    start = 0
    while True:
        index = text.find("***", start)
        if index < 0:
            break
        tail = text[index + 3 : index + 7]
        end = index + 7
        if (
            len(tail) == 4
            and all(character.isalnum() or character in "_-" for character in tail)
            and (index == 0 or not (text[index - 1].isalnum() or text[index - 1] in "_*-"))
            and (end == len(text) or not (text[end].isalnum() or text[end] in "_-"))
        ):
            found.append((text[index:end], (index, end)))
        start = index + 3
    return tuple(found)


def extract_protected_tokens(text: str) -> frozenset[str]:
    occupied: list[tuple[int, int]] = []
    tokens: list[str] = []
    for token, span in _masked_tokens(text):
        occupied.append(span)
        tokens.append(token)
    for pattern in (_DATE, _NUMBER, _ASCII):
        for match in pattern.finditer(text):
            span = match.span()
            if _overlaps(span, occupied):
                continue
            occupied.append(span)
            tokens.append(match.group(0))
    return frozenset(tokens)


def _canonical_display(value: object) -> str:
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is int:
        return str(value)
    if type(value) is str:
        return value
    raise ValueError("business.invalid_fact_value")


def _valid_fact_value(value_type: str, transform_id: str, value: object) -> bool:
    if value_type == "boolean":
        return transform_id == "identity_scalar" and type(value) is bool
    if value_type == "integer":
        return transform_id == "identity_scalar" and type(value) is int and abs(value) <= 2**53 - 1
    if value_type == "decimal":
        return transform_id == "decimal_2" and type(value) is str and re.fullmatch(r"-?(?:0|[1-9][0-9]*)\.[0-9]{2}", value) is not None
    if value_type in {"date", "datetime"}:
        return transform_id == "date_only" and type(value) is str and _DATE.fullmatch(value) is not None
    if value_type == "enum":
        return transform_id == "enum_code" and type(value) is str and bool(value)
    if value_type == "text":
        return transform_id == "bounded_text" and type(value) is str and bool(value)
    if value_type == "identifier":
        return transform_id in {"bounded_text", "mask_keep_last4"} and type(value) is str and bool(value)
    return False


class BusinessAnswerGroundingPolicy:
    def validate(self, input: GroundingInput) -> GroundingDecision:
        try:
            payload = input.safe_payload
            if set(payload) != {"schema_version", "policy_version", "config_snapshot_id", "facts", "presentation", "coverage"}:
                return self._reject()
            if (
                payload.get("schema_version") != 1
                or payload.get("policy_version") != "business-egress-v1"
                or type(payload.get("config_snapshot_id")) is not str
                or _HEX_64.fullmatch(str(payload.get("config_snapshot_id"))) is None
            ):
                return self._reject()
            presentation = payload.get("presentation")
            facts_value = payload.get("facts")
            coverage = payload.get("coverage")
            if (
                not isinstance(presentation, Mapping)
                or set(presentation) != {"mode", "action_id"}
                or presentation.get("mode") != "business_facts"
                or presentation.get("action_id") != input.capability_id
                or not isinstance(coverage, Mapping)
                or set(coverage) != {"truncated"}
                or type(coverage.get("truncated")) is not bool
                or not isinstance(facts_value, tuple)
                or not 1 <= len(facts_value) <= 20
            ):
                return self._reject()
            facts: dict[str, str] = {}
            for index, raw in enumerate(facts_value, 1):
                if not isinstance(raw, Mapping) or set(raw) != {"fact_id", "value_type", "value", "transform_id", "source"}:
                    return self._reject()
                fact_id = raw.get("fact_id")
                value_type = raw.get("value_type")
                transform_id = raw.get("transform_id")
                source = raw.get("source")
                if (
                    fact_id != f"fact-{index:04d}"
                    or type(fact_id) is not str
                    or _FACT_ID.fullmatch(fact_id) is None
                    or type(value_type) is not str
                    or value_type not in _VALUE_TYPES
                    or type(transform_id) is not str
                    or transform_id not in _TRANSFORMS
                    or not isinstance(source, Mapping)
                    or set(source) != {"record_ref", "field_id"}
                    or type(source.get("record_ref")) is not str
                    or _RECORD_REF.fullmatch(str(source.get("record_ref"))) is None
                    or type(source.get("field_id")) is not str
                    or _FIELD_ID.fullmatch(str(source.get("field_id"))) is None
                    or not _valid_fact_value(value_type, transform_id, raw.get("value"))
                ):
                    return self._reject()
                facts[fact_id] = _canonical_display(raw.get("value"))
            used = set(input.candidate.used_fact_ids)
            markers = set(_MARKER.findall(input.candidate.answer))
            if not used or used != markers or not used.issubset(facts):
                return self._reject()
            for segment in _SPLIT.split(input.candidate.answer):
                stripped = segment.strip()
                if not stripped or stripped in {"查询结果：", "根据可用数据："}:
                    continue
                refs = _MARKER.findall(stripped)
                if not refs or any(ref not in facts for ref in refs):
                    return self._reject()
                unmarked = _MARKER.sub(" ", stripped)
                if any(facts[ref] not in unmarked for ref in refs):
                    return self._reject()
                observed_tokens = extract_protected_tokens(unmarked)
                allowed_tokens = frozenset(
                    token
                    for ref in refs
                    for token in extract_protected_tokens(facts[ref])
                )
                if not observed_tokens.issubset(allowed_tokens):
                    return self._reject()
            if input.candidate.unsupported_claims:
                return self._reject()
            if coverage.get("truncated") is True:
                normalized = unicodedata.normalize("NFKC", input.candidate.answer).casefold()
                if any(item in normalized for item in ("全部", "唯一", "完整", "没有其他", "all", "only", "complete", "no other")):
                    return self._reject()
            return GroundingDecision(accepted=True)
        except Exception:
            return self._reject()

    @staticmethod
    def _reject() -> GroundingDecision:
        return GroundingDecision(accepted=False, reason=GroundingRejectionReason.DOMAIN_POLICY_REJECTED)
