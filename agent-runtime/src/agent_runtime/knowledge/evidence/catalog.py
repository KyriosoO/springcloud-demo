from __future__ import annotations

import hashlib
import json
import re
import unicodedata

from agent_runtime.knowledge.evidence.contracts import (
    DocumentPolicyBinding,
    KnowledgeEgressField,
    KnowledgeEgressPolicy,
    PolicyCatalogSnapshot,
)


class KnowledgePolicyCatalogError(ValueError):
    pass


_SAFE_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")
_LOWER_HEX_64 = re.compile(r"[0-9a-f]{64}")


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
    """Frozen catalog reader; this P3 slice accepts synthetic snapshots only."""

    __slots__ = ("_bindings", "_policies", "snapshot")

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
        ):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_invalid")
        policies = {item.policy_ref: item for item in snapshot.policies}
        bindings = {item.document_id: item for item in snapshot.bindings}
        if len(policies) != len(snapshot.policies) or len(bindings) != len(snapshot.bindings):
            raise KnowledgePolicyCatalogError("knowledge.policy_catalog_conflict")
        for policy in snapshot.policies:
            if (
                _SAFE_ID.fullmatch(policy.policy_ref) is None
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
