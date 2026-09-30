"""Read-only corpus snapshot attestation for one Knowledge rebuild measurement.

Run with the pinned knowledge-corpus-tools project environment, not the Runtime
environment. This reuses its canonical full-record fingerprint implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time
from typing import Any, cast

import httpx

from knowledge_corpus_tools.b_id_mapping_v1 import MappingScanSpec, scan_id_mapping_v1


def _fail(reason: str) -> None:
    raise ValueError("knowledge.measure.snapshot_" + reason)


def _object(raw: bytes) -> dict[str, Any]:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                _fail("duplicate_key")
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: _fail("nonfinite"))
    if type(value) is not dict:
        _fail("invalid_json")
    return cast(dict[str, Any], value)


def attest(*, manifest_path: Path, expected_sha256: str, output_path: Path,
           es_origin: str = "http://127.0.0.1:9200") -> dict[str, Any]:
    if es_origin != "http://127.0.0.1:9200" or output_path.exists():
        _fail("invalid_target")
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        _fail("manifest_drift")
    manifest = _object(raw)
    bindings = manifest["indexBindings"]
    if type(bindings) is not dict or set(bindings) != {"tax.policy", "tax.law"}:
        _fail("bindings_invalid")
    policy, law = bindings["tax.policy"], bindings["tax.law"]
    count = policy["recordCount"]
    if (manifest["aliasFlags"] not in ({}, {"is_write_index": False})
            or manifest["snapshotPreflightEsHttpRequests"] != 4 + (count + 249) // 250
            or manifest["snapshotPostflightEsHttpRequests"] != 4 + (count + 249) // 250):
        _fail("read_budget_invalid")
    if any(policy[key] != law[key] for key in ("readAlias", "indexName", "indexUuid",
                                                "mappingVersion", "mappingSha256", "fullFingerprint", "recordCount")):
        _fail("bindings_invalid")
    for domain, profile_id in (("tax.policy", "tax-policy-v1"), ("tax.law", "tax-law-v1")):
        item = bindings[domain]
        canonical = "\n".join((profile_id, item["indexName"], item["indexUuid"],
                               "tax-knowledge-search-v1", item["mappingVersion"]))
        if (hashlib.sha256(canonical.encode("utf-8")).hexdigest() != item["snapshotId"]
                or item["readPolicyVersion"] != "tax-public-authenticated-v1"):
            _fail("profile_drift")
    with httpx.Client(base_url=es_origin, follow_redirects=False, trust_env=False, timeout=30.0) as client:
        def check_alias() -> None:
            response = client.get(f"/_alias/{policy['readAlias']}")
            if response.status_code != 200 or len(response.content) > 65536:
                _fail("alias_unavailable")
            alias = _object(response.content)
            if (set(alias) != {policy["indexName"]}
                    or alias[policy["indexName"]].get("aliases", {}).get(policy["readAlias"]) != manifest["aliasFlags"]):
                _fail("alias_drift")
        check_alias()
        scan = scan_id_mapping_v1(MappingScanSpec(
            index_name=policy["indexName"], index_uuid=policy["indexUuid"],
            mapping_sha256=policy["mappingSha256"], source_fingerprint=policy["fullFingerprint"],
            record_count=count, max_http_requests=1 + (count + 249) // 250), client=client)
        if scan.record_count != count or scan.mapping_version != policy["mappingVersion"]:
            _fail("scan_drift")
        check_alias()
        response = client.get(f"/{policy['indexName']}/_settings")
        if response.status_code != 200 or len(response.content) > 65536:
            _fail("uuid_recheck_failed")
        settings = _object(response.content)
        if settings.get(policy["indexName"], {}).get("settings", {}).get("index", {}).get("uuid") != policy["indexUuid"]:
            _fail("uuid_recheck_failed")
    value = {"schemaVersion": 1, "status": "passed", "runId": manifest["runId"],
             "manifestSha256": expected_sha256, "indexName": policy["indexName"],
             "indexUuid": policy["indexUuid"], "fullFingerprint": policy["fullFingerprint"],
             "recordCount": count, "createdAtUnixMs": time.time_ns() // 1_000_000}
    encoded = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    with output_path.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    attest(manifest_path=args.manifest, expected_sha256=args.manifest_sha256, output_path=args.output)


if __name__ == "__main__":
    main()
