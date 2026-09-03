from __future__ import annotations

import hashlib
import importlib.resources
import json
import re
import unicodedata
from dataclasses import replace
from typing import Any, Self

from agent_runtime.knowledge.evidence.contracts import (
    DocumentPolicyBinding,
    KnowledgeEgressDisposition,
    KnowledgeEgressField,
    KnowledgeEgressPolicy,
    PolicyCatalogSnapshot,
)


class KnowledgePolicyCatalogError(ValueError):
    pass


EXPECTED_KNOWLEDGE_EGRESS_CATALOG_SHA256 = "442761355510165265cb2eee3be8ee8a310c38ab7796a998ff1863073dbbd698"
_CATALOG_RESOURCE = "egress-policy-catalog.json"
EXPECTED_CURRENT_KNOWLEDGE_EGRESS_CATALOG_SHA256 = "c6d2954a32a38527cf975a74f1a666ac0edbc3cd65561f35472e621dd1400f32"
_CURRENT_CATALOG_RESOURCE = "egress-policy-catalog-v2.json"
_MAX_CATALOG_BYTES = 4 * 1024 * 1024
_SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}")
_TOP_LEVEL_KEYS = {
    "schemaVersion",
    "catalogVersion",
    "authorityId",
    "exportId",
    "sourceRevision",
    "policies",
    "bindings",
}
_POLICY_KEYS = {
    "policyRef",
    "policyVersion",
    "disposition",
    "allowedFields",
    "maxContentCodePoints",
}
_BINDING_KEYS = {
    "documentId",
    "policyRef",
    "policyVersion",
    "allowedIndexSnapshotIds",
}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        result[key] = value
    return result


def _reject_constant(_: str) -> None:
    raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")


def _validate_text_tree(value: object) -> None:
    if isinstance(value, str):
        if any(
            unicodedata.category(character) in {"Cc", "Cs"}
            for character in value
        ):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_text_tree(key)
            _validate_text_tree(item)
        return
    if isinstance(value, list):
        for item in value:
            _validate_text_tree(item)


def _strict_json_object(raw: bytes) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except KnowledgePolicyCatalogError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid") from exc
    if type(value) is not dict:
        raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
    _validate_text_tree(value)
    return value


def _exact_keys(value: object, expected: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != expected:
        raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
    return value


def _parse_snapshot(raw: bytes, *, source_sha256: str) -> PolicyCatalogSnapshot:
    value = _exact_keys(_strict_json_object(raw), _TOP_LEVEL_KEYS)
    policies_raw = value["policies"]
    bindings_raw = value["bindings"]
    if (
        type(value["schemaVersion"]) is not int
        or any(
            type(value[key]) is not str
            for key in ("catalogVersion", "authorityId", "exportId", "sourceRevision")
        )
        or type(policies_raw) is not list
        or type(bindings_raw) is not list
    ):
        raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
    policies: list[KnowledgeEgressPolicy] = []
    for raw_policy in policies_raw:
        policy = _exact_keys(raw_policy, _POLICY_KEYS)
        allowed_fields = policy["allowedFields"]
        if (
            type(policy["policyRef"]) is not str
            or type(policy["policyVersion"]) is not str
            or type(policy["disposition"]) is not str
            or type(allowed_fields) is not list
            or any(type(item) is not str for item in allowed_fields)
            or len(set(allowed_fields)) != len(allowed_fields)
            or type(policy["maxContentCodePoints"]) is not int
        ):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        try:
            fields = frozenset(KnowledgeEgressField(item) for item in allowed_fields)
            disposition = KnowledgeEgressDisposition(policy["disposition"])
        except (TypeError, ValueError) as exc:
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid") from exc
        policies.append(
            KnowledgeEgressPolicy(
                policy_ref=policy["policyRef"],
                policy_version=policy["policyVersion"],
                disposition=disposition,
                allowed_fields=fields,
                max_content_code_points=policy["maxContentCodePoints"],
            )
        )
    bindings: list[DocumentPolicyBinding] = []
    for raw_binding in bindings_raw:
        binding = _exact_keys(raw_binding, _BINDING_KEYS)
        snapshots = binding["allowedIndexSnapshotIds"]
        if (
            type(binding["documentId"]) is not str
            or type(binding["policyRef"]) is not str
            or type(binding["policyVersion"]) is not str
            or type(snapshots) is not list
            or any(type(item) is not str for item in snapshots)
            or len(set(snapshots)) != len(snapshots)
        ):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        bindings.append(
            DocumentPolicyBinding(
                document_id=binding["documentId"],
                policy_ref=binding["policyRef"],
                policy_version=binding["policyVersion"],
                allowed_index_snapshot_ids=frozenset(snapshots),
            )
        )
    snapshot = PolicyCatalogSnapshot(
        schema_version=value["schemaVersion"],
        catalog_version=value["catalogVersion"],
        authority_id=value["authorityId"],
        export_id=value["exportId"],
        source_revision=value["sourceRevision"],
        source_sha256=source_sha256,
        canonical_fingerprint="0" * 64,
        policies=tuple(policies),
        bindings=tuple(bindings),
    )
    return replace(snapshot, canonical_fingerprint=canonical_policy_fingerprint(snapshot))


def canonical_policy_fingerprint(snapshot: PolicyCatalogSnapshot) -> str:
    material = {
        "schemaVersion": snapshot.schema_version,
        "catalogVersion": snapshot.catalog_version,
        "authorityId": snapshot.authority_id,
        "exportId": snapshot.export_id,
        "sourceRevision": snapshot.source_revision,
        "sourceSha256": snapshot.source_sha256,
        "policies": [
            {
                "policyRef": item.policy_ref,
                "policyVersion": item.policy_version,
                "disposition": item.disposition.value,
                "allowedFields": sorted(field.value for field in item.allowed_fields),
                "maxContentCodePoints": item.max_content_code_points,
            }
            for item in snapshot.policies
        ],
        "bindings": [
            {
                "documentId": item.document_id,
                "policyRef": item.policy_ref,
                "policyVersion": item.policy_version,
                "allowedIndexSnapshotIds": sorted(item.allowed_index_snapshot_ids),
            }
            for item in snapshot.bindings
        ],
    }
    payload = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class KnowledgeEgressPolicyCatalog:
    """Frozen catalog reader with a code-bound production package resource."""

    __slots__ = ("_bindings", "_policies", "snapshot")

    @classmethod
    def load_v1_resource(cls) -> Self:
        return cls._load_resource(
            resource_name=_CATALOG_RESOURCE,
            expected_sha256=EXPECTED_KNOWLEDGE_EGRESS_CATALOG_SHA256,
        )

    @classmethod
    def load_current_resource(cls) -> Self:
        return cls._load_resource(
            resource_name=_CURRENT_CATALOG_RESOURCE,
            expected_sha256=EXPECTED_CURRENT_KNOWLEDGE_EGRESS_CATALOG_SHA256,
        )

    @classmethod
    def _load_resource(cls, *, resource_name: str, expected_sha256: str) -> Self:
        try:
            resource = importlib.resources.files(__package__).joinpath(resource_name)
            with resource.open("rb") as stream:
                raw = stream.read(_MAX_CATALOG_BYTES + 1)
        except (FileNotFoundError, OSError) as exc:
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_unavailable") from exc
        if len(raw) > _MAX_CATALOG_BYTES:
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        source_sha256 = hashlib.sha256(raw).hexdigest()
        if source_sha256 != expected_sha256:
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_hash_mismatch")
        return cls(_parse_snapshot(raw, source_sha256=source_sha256))

    def __init__(self, snapshot: PolicyCatalogSnapshot) -> None:
        metadata = (
            snapshot.catalog_version,
            snapshot.authority_id,
            snapshot.export_id,
            snapshot.source_revision,
        )
        if (
            snapshot.schema_version != 1
            or any(type(item) is not str or _SAFE_ID.fullmatch(item) is None for item in metadata)
            or type(snapshot.source_sha256) is not str
            or _LOWER_HEX_64.fullmatch(snapshot.source_sha256) is None
            or type(snapshot.canonical_fingerprint) is not str
            or _LOWER_HEX_64.fullmatch(snapshot.canonical_fingerprint) is None
            or not 1 <= len(snapshot.policies) <= 64
            or not 1 <= len(snapshot.bindings) <= 20000
            or any(not isinstance(item, KnowledgeEgressPolicy) for item in snapshot.policies)
            or any(not isinstance(item, DocumentPolicyBinding) for item in snapshot.bindings)
        ):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        if any(
            type(item.policy_ref) is not str
            or type(item.policy_version) is not str
            or not isinstance(item.disposition, KnowledgeEgressDisposition)
            or not isinstance(item.allowed_fields, frozenset)
            or any(not isinstance(field, KnowledgeEgressField) for field in item.allowed_fields)
            or type(item.max_content_code_points) is not int
            for item in snapshot.policies
        ) or any(
            type(item.document_id) is not str
            or type(item.policy_ref) is not str
            or type(item.policy_version) is not str
            or not isinstance(item.allowed_index_snapshot_ids, frozenset)
            or any(type(value) is not str for value in item.allowed_index_snapshot_ids)
            for item in snapshot.bindings
        ):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        policies = {item.policy_ref: item for item in snapshot.policies}
        bindings = {item.document_id: item for item in snapshot.bindings}
        if len(policies) != len(snapshot.policies) or len(bindings) != len(snapshot.bindings):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_conflict")
        for policy in snapshot.policies:
            if (
                type(policy.policy_ref) is not str
                or type(policy.policy_version) is not str
                or _SAFE_ID.fullmatch(policy.policy_ref) is None
                or _SAFE_ID.fullmatch(policy.policy_version) is None
                or (
                    policy.disposition.value == "allow_minimal"
                    and (
                        not 1 <= policy.max_content_code_points <= 4096
                        or KnowledgeEgressField.CONTENT not in policy.allowed_fields
                    )
                )
                or (
                    policy.disposition.value == "deny"
                    and (policy.allowed_fields or policy.max_content_code_points != 0)
                )
            ):
                raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        for binding in snapshot.bindings:
            normalized_document_id = unicodedata.normalize("NFC", binding.document_id)
            if (
                normalized_document_id != binding.document_id
                or not 1 <= len(binding.document_id) <= 256
                or any(unicodedata.category(character) == "Cc" for character in binding.document_id)
                or _SAFE_ID.fullmatch(binding.policy_ref) is None
                or _SAFE_ID.fullmatch(binding.policy_version) is None
                or not 1 <= len(binding.allowed_index_snapshot_ids) <= 8
                or any(_LOWER_HEX_64.fullmatch(value) is None for value in binding.allowed_index_snapshot_ids)
            ):
                raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        if any(item.policy_ref not in policies or policies[item.policy_ref].policy_version != item.policy_version for item in snapshot.bindings):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        if canonical_policy_fingerprint(snapshot) != snapshot.canonical_fingerprint:
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        self.snapshot = snapshot
        self._policies = policies
        self._bindings = bindings

    def resolve(
        self,
        *,
        document_id: str,
        policy_ref: str,
        index_snapshot_id: str,
    ) -> tuple[KnowledgeEgressPolicy, DocumentPolicyBinding]:
        binding = self._bindings.get(document_id)
        if binding is None:
            raise KnowledgePolicyCatalogError("knowledge.policy_missing")
        if binding.policy_ref != policy_ref:
            raise KnowledgePolicyCatalogError("knowledge.policy_conflict")
        if index_snapshot_id not in binding.allowed_index_snapshot_ids:
            raise KnowledgePolicyCatalogError("knowledge.policy_missing")
        policy = self._policies.get(policy_ref)
        if policy is None or policy.policy_version != binding.policy_version:
            raise KnowledgePolicyCatalogError("knowledge.policy_conflict")
        return policy, binding
