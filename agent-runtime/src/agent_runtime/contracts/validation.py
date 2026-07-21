from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import TypeVar

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError


T = TypeVar("T", bound=BaseModel)
_ALLOWED_SCHEMAS = frozenset({"ContractMetadata", "RuntimeError", "RuntimeReadiness"})


class ContractPayloadValidationError(ValueError):
    code = "CONTRACT_PAYLOAD_INVALID"

    def __init__(self) -> None:
        super().__init__(self.code)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContractPayloadValidationError()
        result[key] = value
    return result


@lru_cache(maxsize=len(_ALLOWED_SCHEMAS))
def _load_validator(schema_name: str) -> Draft202012Validator:
    if schema_name not in _ALLOWED_SCHEMAS:
        raise ContractPayloadValidationError()
    try:
        bundle = json.loads(
            files("agent_runtime.contracts")
            .joinpath("contract_schema.json")
            .read_text(encoding="utf-8")
        )
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$defs": bundle["$defs"],
            "$ref": f"#/$defs/{schema_name}",
        }
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except ContractPayloadValidationError:
        raise
    except Exception:
        raise ContractPayloadValidationError() from None


def parse_contract_payload(raw_json: str | bytes, schema_name: str, model_type: type[T]) -> T:
    if model_type.__module__ != "agent_runtime.contracts.generated_models":
        raise ContractPayloadValidationError()
    try:
        payload = json.loads(raw_json, object_pairs_hook=_reject_duplicate_keys)
        _load_validator(schema_name).validate(payload)
        return model_type.model_validate(payload)
    except ContractPayloadValidationError:
        raise
    except Exception:
        raise ContractPayloadValidationError() from None
