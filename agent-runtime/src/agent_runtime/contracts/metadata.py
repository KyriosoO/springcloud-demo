from __future__ import annotations

import json
import re
from importlib.resources import files

from pydantic import ValidationError

from .generated_models import ContractMetadata, RuntimeReadiness, Status


_METADATA_FIELDS = {
    "capabilities",
    "contractFingerprint",
    "contractVersion",
    "lockFormatVersion",
    "sourceSha256",
}


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("CONTRACT_METADATA_INVALID")
        result[key] = value
    return result


def _parse_contract_metadata(payload: object) -> ContractMetadata:
    if not isinstance(payload, dict) or set(payload) != _METADATA_FIELDS:
        raise ValueError("CONTRACT_METADATA_INVALID")
    source_sha = payload.get("sourceSha256")
    capabilities = payload.get("capabilities")
    if (
        payload.get("lockFormatVersion") != 1
        or not isinstance(source_sha, str)
        or not re.fullmatch(r"[a-f0-9]{64}", source_sha)
        or payload.get("contractFingerprint") != f"sha256:{source_sha}"
        or not isinstance(capabilities, list)
        or any(not isinstance(value, str) or not value for value in capabilities)
        or capabilities != sorted(set(capabilities))
    ):
        raise ValueError("CONTRACT_METADATA_INVALID")
    try:
        return ContractMetadata.model_validate(
            {
                "contractVersion": payload["contractVersion"],
                "contractFingerprint": payload["contractFingerprint"],
                "capabilities": capabilities,
            }
        )
    except ValidationError:
        raise ValueError("CONTRACT_METADATA_INVALID") from None


def load_contract_metadata() -> ContractMetadata:
    try:
        payload = json.loads(
            files("agent_runtime.contracts")
            .joinpath("contract_metadata.json")
            .read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
        return _parse_contract_metadata(payload)
    except (OSError, UnicodeError, TypeError, ValueError):
        raise ValueError("CONTRACT_METADATA_INVALID") from None


def contract_readiness() -> RuntimeReadiness:
    return RuntimeReadiness(status=Status.contract_ready, metadata=load_contract_metadata(), reasons=[])
