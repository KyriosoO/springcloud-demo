from __future__ import annotations

import json
import re
from importlib.resources import files

from .generated_models import ContractMetadata, RuntimeReadiness, Status


def load_contract_metadata() -> ContractMetadata:
    payload = json.loads(
        files("agent_runtime.contracts")
        .joinpath("contract_metadata.json")
        .read_text(encoding="utf-8")
    )
    if payload.get("lockFormatVersion") != 1:
        raise ValueError("CONTRACT_METADATA_INVALID")
    source_sha = payload.get("sourceSha256", "")
    if not re.fullmatch(r"[a-f0-9]{64}", source_sha):
        raise ValueError("CONTRACT_METADATA_INVALID")
    if payload.get("contractFingerprint") != f"sha256:{source_sha}":
        raise ValueError("CONTRACT_METADATA_INVALID")
    if payload.get("capabilities") != sorted(set(payload.get("capabilities", []))):
        raise ValueError("CONTRACT_METADATA_INVALID")
    return ContractMetadata.model_validate(
        {
            "contractVersion": payload["contractVersion"],
            "contractFingerprint": payload["contractFingerprint"],
            "capabilities": payload["capabilities"],
        }
    )


def contract_readiness() -> RuntimeReadiness:
    return RuntimeReadiness(status=Status.contract_ready, metadata=load_contract_metadata(), reasons=[])
