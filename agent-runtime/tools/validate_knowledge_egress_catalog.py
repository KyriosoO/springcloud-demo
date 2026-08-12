from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any


AGENT_RUNTIME = Path(__file__).resolve().parents[1]
REPOSITORY = AGENT_RUNTIME.parent
SOURCE = AGENT_RUNTIME / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from agent_runtime.knowledge.evidence.catalog import (  # noqa: E402
    EXPECTED_KNOWLEDGE_EGRESS_CATALOG_SHA256,
    KnowledgeEgressPolicyCatalog,
)


CATALOG_PATH = SOURCE / "agent_runtime/knowledge/evidence/egress-policy-catalog.json"
TOP_KEYS = {
    "schemaVersion",
    "workPackageId",
    "recordedAt",
    "authorizationReference",
    "authority",
    "sourceSnapshot",
    "metadataSha256",
    "bindingsSha256",
    "catalog",
    "documents",
}
AUTHORITY_KEYS = {
    "authorityId",
    "exportId",
    "sourceRevision",
    "classification",
    "initialAuthority",
    "decision",
}
SNAPSHOT_KEYS = {
    "readAlias",
    "readIndex",
    "readIndexUuid",
    "mappingVersion",
    "mappingSha256",
    "retrievalProfileVersion",
    "profiles",
    "chunkCount",
    "uniqueDocumentCount",
    "sourceAndReadIndexDigestSha256",
    "retrievalEvidencePath",
    "retrievalEvidenceSha256",
}
PROFILE_KEYS = {
    "logicalDomainId",
    "retrievalProfileId",
    "indexSnapshotId",
    "categoryValues",
}
DOCUMENT_KEYS = {"documentId", "policyRef", "logicalDomainIds"}
CATALOG_KEYS = {"path", "catalogVersion", "sha256"}
HEX = frozenset("0123456789abcdef")


class ValidationError(ValueError):
    pass


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("knowledge.egress_manifest_duplicate_key")
        result[key] = value
    return result


def reject_constant(_: str) -> None:
    raise ValidationError("knowledge.egress_manifest_non_finite")


def reject_controls(value: object) -> None:
    if isinstance(value, str):
        if any(unicodedata.category(character) in {"Cc", "Cs"} for character in value):
            raise ValidationError("knowledge.egress_manifest_invalid_text")
    elif isinstance(value, dict):
        for key, item in value.items():
            reject_controls(key)
            reject_controls(item)
    elif isinstance(value, list):
        for item in value:
            reject_controls(item)


def load_object(path: Path, *, max_bytes: int) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes:
        raise ValidationError("knowledge.egress_manifest_size_invalid")
    try:
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except ValidationError:
        raise
    except (UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValidationError("knowledge.egress_manifest_json_invalid") from exc
    if type(value) is not dict:
        raise ValidationError("knowledge.egress_manifest_object_required")
    reject_controls(value)
    return value, raw


def exact(value: object, keys: set[str], code: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        raise ValidationError(code)
    return value


def lower_hex_64(value: object) -> bool:
    return type(value) is str and len(value) == 64 and set(value) <= HEX


def canonical_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate(catalog_path: Path, manifest_path: Path) -> dict[str, object]:
    if catalog_path.resolve() != CATALOG_PATH.resolve():
        raise ValidationError("knowledge.egress_catalog_path_invalid")
    catalog_raw = catalog_path.read_bytes()
    catalog_sha = hashlib.sha256(catalog_raw).hexdigest()
    if catalog_sha != EXPECTED_KNOWLEDGE_EGRESS_CATALOG_SHA256:
        raise ValidationError("knowledge.egress_catalog_hash_mismatch")
    loaded = KnowledgeEgressPolicyCatalog.load_v1_resource()
    manifest, _ = load_object(manifest_path, max_bytes=4 * 1024 * 1024)
    exact(manifest, TOP_KEYS, "knowledge.egress_manifest_schema_invalid")
    if (
        manifest["schemaVersion"] != 1
        or manifest["workPackageId"] != "WP-K-EGRESS-01"
        or manifest["authorizationReference"] != "P3_00:GATE-022"
        or not lower_hex_64(manifest["metadataSha256"])
        or not lower_hex_64(manifest["bindingsSha256"])
    ):
        raise ValidationError("knowledge.egress_manifest_provenance_invalid")

    authority = exact(manifest["authority"], AUTHORITY_KEYS, "knowledge.egress_manifest_authority_invalid")
    if (
        authority["classification"] != "public_knowledge"
        or authority["initialAuthority"] != "project-maintainer"
        or authority["decision"] != "allow_minimal_summary"
        or authority["sourceRevision"] != f"esmeta-{manifest['metadataSha256']}"
    ):
        raise ValidationError("knowledge.egress_manifest_authority_invalid")
    snapshot = exact(manifest["sourceSnapshot"], SNAPSHOT_KEYS, "knowledge.egress_manifest_snapshot_invalid")
    profiles = snapshot["profiles"]
    if type(profiles) is not list or len(profiles) != 2:
        raise ValidationError("knowledge.egress_manifest_snapshot_invalid")
    expected_domains = ("tax.policy", "tax.law")
    snapshot_by_domain: dict[str, str] = {}
    for expected_domain, raw_profile in zip(expected_domains, profiles, strict=True):
        profile = exact(raw_profile, PROFILE_KEYS, "knowledge.egress_manifest_profile_invalid")
        categories = profile["categoryValues"]
        if (
            profile["logicalDomainId"] != expected_domain
            or not lower_hex_64(profile["indexSnapshotId"])
            or type(categories) is not list
            or not categories
            or len(set(categories)) != len(categories)
            or any(type(item) is not str or not item for item in categories)
        ):
            raise ValidationError("knowledge.egress_manifest_profile_invalid")
        snapshot_by_domain[expected_domain] = profile["indexSnapshotId"]

    documents = manifest["documents"]
    if type(documents) is not list or not 1 <= len(documents) <= 20000:
        raise ValidationError("knowledge.egress_manifest_documents_invalid")
    normalized_documents: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_document in documents:
        document = exact(raw_document, DOCUMENT_KEYS, "knowledge.egress_manifest_document_invalid")
        document_id = document["documentId"]
        domains = document["logicalDomainIds"]
        if (
            type(document_id) is not str
            or not 1 <= len(document_id) <= 256
            or unicodedata.normalize("NFC", document_id) != document_id
            or document_id in seen
            or document["policyRef"] != "public:tax_policy"
            or type(domains) is not list
            or not domains
            or domains != [item for item in expected_domains if item in domains]
            or len(set(domains)) != len(domains)
        ):
            raise ValidationError("knowledge.egress_manifest_document_invalid")
        seen.add(document_id)
        normalized_documents.append(document)
    if [item["documentId"] for item in normalized_documents] != sorted(seen):
        raise ValidationError("knowledge.egress_manifest_document_order_invalid")
    if snapshot["uniqueDocumentCount"] != len(documents) or snapshot["chunkCount"] != 14783:
        raise ValidationError("knowledge.egress_manifest_count_invalid")

    metadata_material = {
        key: value
        for key, value in snapshot.items()
        if key not in {"sourceAndReadIndexDigestSha256", "retrievalEvidencePath", "retrievalEvidenceSha256"}
    }
    metadata_material["documents"] = documents
    if canonical_sha(metadata_material) != manifest["metadataSha256"]:
        raise ValidationError("knowledge.egress_manifest_metadata_hash_mismatch")
    bindings = [
        {
            "documentId": item["documentId"],
            "policyRef": item["policyRef"],
            "policyVersion": "1",
            "allowedIndexSnapshotIds": [snapshot_by_domain[domain] for domain in item["logicalDomainIds"]],
        }
        for item in documents
    ]
    if canonical_sha(bindings) != manifest["bindingsSha256"]:
        raise ValidationError("knowledge.egress_manifest_bindings_hash_mismatch")

    catalog_meta = exact(manifest["catalog"], CATALOG_KEYS, "knowledge.egress_manifest_catalog_invalid")
    if (
        catalog_meta["path"] != CATALOG_PATH.relative_to(REPOSITORY).as_posix()
        or catalog_meta["sha256"] != catalog_sha
        or catalog_meta["catalogVersion"] != loaded.snapshot.catalog_version
        or authority["authorityId"] != loaded.snapshot.authority_id
        or authority["exportId"] != loaded.snapshot.export_id
        or authority["sourceRevision"] != loaded.snapshot.source_revision
    ):
        raise ValidationError("knowledge.egress_manifest_catalog_invalid")
    snapshot_rank = {
        snapshot_id: rank
        for rank, snapshot_id in enumerate(snapshot_by_domain.values())
    }
    actual_bindings = [
        {
            "documentId": item.document_id,
            "policyRef": item.policy_ref,
            "policyVersion": item.policy_version,
            "allowedIndexSnapshotIds": sorted(
                item.allowed_index_snapshot_ids,
                key=lambda value: snapshot_rank.get(value, len(snapshot_rank)),
            ),
        }
        for item in loaded.snapshot.bindings
    ]
    if actual_bindings != bindings:
        raise ValidationError("knowledge.egress_catalog_binding_conflict")

    evidence_path = REPOSITORY / snapshot["retrievalEvidencePath"]
    evidence_raw = evidence_path.read_bytes()
    if hashlib.sha256(evidence_raw).hexdigest() != snapshot["retrievalEvidenceSha256"]:
        raise ValidationError("knowledge.egress_manifest_retrieval_evidence_hash_mismatch")
    evidence = json.loads(evidence_raw)
    frozen = evidence["indexSnapshot"]
    if (
        frozen["readAlias"] != snapshot["readAlias"]
        or frozen["readIndex"] != snapshot["readIndex"]
        or frozen["readIndexUuid"] != snapshot["readIndexUuid"]
        or frozen["mappingVersion"] != snapshot["mappingVersion"]
        or frozen["documentCount"] != snapshot["chunkCount"]
        or frozen["sourceAndReadIndexDigestSha256"] != snapshot["sourceAndReadIndexDigestSha256"]
        or frozen["writeBlocked"] is not True
    ):
        raise ValidationError("knowledge.egress_manifest_retrieval_evidence_conflict")
    return {
        "status": "passed",
        "catalogSha256": catalog_sha,
        "metadataSha256": manifest["metadataSha256"],
        "bindingsSha256": manifest["bindingsSha256"],
        "documentCount": len(documents),
        "chunkCount": snapshot["chunkCount"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.catalog, args.manifest)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        code = str(exc) if str(exc).startswith("knowledge.") else "knowledge.egress_catalog_validation_failed"
        print(json.dumps({"status": "failed", "code": code}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
