"""DR-KRET-024: extend verified document bindings to an equivalent new snapshot.

This is offline preparation only. It does not select the Runtime resource, grant
new policies, publish an alias, or change any existing catalog bytes.
"""
from __future__ import annotations

from collections.abc import Mapping
import copy
import hashlib
import re
from typing import Any

from knowledge_corpus_tools.vector_candidate import canonical_bytes

DOMAINS = frozenset({"tax.policy", "tax.law"})
_HEX = re.compile(r"[a-f0-9]{64}")
_ID = re.compile(r"[A-Za-z0-9._:-]{1,256}")


def profile_snapshot(profile_id: str, index: str, uuid: str, mapping_version: str) -> str:
    """Same canonical input as Java KnowledgeProfileVerifier.snapshot."""
    if profile_id not in {"tax-policy-v1", "tax-law-v1"} or any(
        type(value) is not str or _ID.fullmatch(value) is None
        for value in (index, uuid, mapping_version)
    ):
        raise ValueError("snapshot_binding_invalid")
    return hashlib.sha256("\n".join((
        profile_id, index, uuid, "tax-knowledge-search-v1", mapping_version,
    )).encode("utf-8")).hexdigest()


def extend_catalog(
    catalog: dict[str, Any], *, members: Mapping[str, tuple[str, frozenset[str]]],
    old_snapshots: Mapping[str, str], new_snapshots: Mapping[str, str],
    export_id: str, source_revision: str,
) -> dict[str, Any]:
    """Preserve all policy/field bounds; add only each actual member's new domain snapshot.

    The caller binds the old catalog's exact reviewed SHA before parsing. The
    generated catalog must also pass the existing Runtime strict loader before
    publication. Membership comes from a full, fingerprint-verified index scan.
    """
    if (set(old_snapshots) != DOMAINS or set(new_snapshots) != DOMAINS
            or len(set(new_snapshots.values())) != 2
            or any(type(value) is not str or _HEX.fullmatch(value) is None
                   for value in (*old_snapshots.values(), *new_snapshots.values()))
            or set(old_snapshots.values()) & set(new_snapshots.values())
            or any(type(value) is not str or _ID.fullmatch(value) is None
                   for value in (export_id, source_revision))):
        raise ValueError("catalog_snapshot_invalid")
    expected_keys = {"schemaVersion", "catalogVersion", "authorityId", "exportId",
                     "sourceRevision", "policies", "bindings"}
    if (type(catalog) is not dict or set(catalog) != expected_keys
            or catalog["catalogVersion"] != "tax-egress-catalog-v2"
            or type(catalog["bindings"]) is not list or not 1 <= len(members) <= 20000):
        raise ValueError("catalog_source_invalid")
    result = copy.deepcopy(catalog)
    seen: set[str] = set()
    for binding in result["bindings"]:
        if type(binding) is not dict or set(binding) != {
            "documentId", "policyRef", "policyVersion", "allowedIndexSnapshotIds",
        }:
            raise ValueError("catalog_binding_invalid")
        identifier = binding["documentId"]
        if type(identifier) is not str or identifier in seen or identifier not in members:
            raise ValueError("catalog_membership_invalid")
        seen.add(identifier)
        policy_ref, domains = members[identifier]
        if (policy_ref != binding["policyRef"] or type(domains) is not frozenset
                or not domains or not domains <= DOMAINS):
            raise ValueError("catalog_membership_invalid")
        old = binding["allowedIndexSnapshotIds"]
        if (type(old) is not list or any(type(value) is not str or _HEX.fullmatch(value) is None for value in old)
                or len(old) != len(set(old))
                or any(old_snapshots[domain] not in old for domain in domains)):
            raise ValueError("catalog_previous_snapshot_missing")
        additions = [new_snapshots[domain] for domain in sorted(domains)]
        if set(additions) & set(old) or len(old) + len(additions) > 8:
            raise ValueError("catalog_snapshot_limit")
        binding["allowedIndexSnapshotIds"] = [*old, *additions]
    if seen != set(members):
        raise ValueError("catalog_membership_invalid")
    result.update(catalogVersion="tax-egress-catalog-v3", exportId=export_id,
                  sourceRevision=source_revision)
    if len(canonical_bytes(result)) > 4 * 1024 * 1024:
        raise ValueError("catalog_size_limit")
    return result
