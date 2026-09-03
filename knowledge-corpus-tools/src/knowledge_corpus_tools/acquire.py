from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from .errors import SafetyError, StateConflict
from .jsonio import sha256_bytes
from .models import AssetManifest
from .safety import canonical_extension, detect_mime, extension_from_name, normalize_official_url, validate_mime


class OfficialAssetAcquirer:
    def __init__(
        self,
        *,
        workspace: Path,
        allowed_hosts: frozenset[str],
        max_asset_bytes: int = 50 * 1024 * 1024,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._workspace = workspace.resolve()
        self._allowed_hosts = allowed_hosts
        self._max_asset_bytes = max_asset_bytes
        self._owned_client = client is None
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=False,
            headers={
                "User-Agent": "Mozilla/5.0 KnowledgeCorpusAudit/1.0",
                "Accept": "text/html,application/pdf,application/msword,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;q=0.9,*/*;q=0.1",
            },
        )

    def close(self) -> None:
        if self._owned_client:
            self._client.close()

    def fetch(
        self,
        *,
        url: str,
        parent_document_id: str,
        official_source_proof: str,
        filename: str | None = None,
    ) -> AssetManifest:
        current = normalize_official_url(url, self._allowed_hosts)
        redirects = 0
        while True:
            with self._client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if redirects >= 3:
                        raise SafetyError("redirect limit exceeded")
                    location = response.headers.get("location")
                    if not location:
                        raise SafetyError("redirect missing location")
                    current = normalize_official_url(urljoin(current, location), self._allowed_hosts)
                    redirects += 1
                    continue
                if response.status_code != 200:
                    raise SafetyError(f"official source HTTP status: {response.status_code}")
                declared_length = response.headers.get("content-length")
                if declared_length and int(declared_length) > self._max_asset_bytes:
                    raise SafetyError("declared asset size exceeds limit")
                body = bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body) > self._max_asset_bytes:
                        raise SafetyError("asset size exceeds limit")
                raw = bytes(body)
                declared_mime = response.headers.get("content-type")
                break
        if not raw:
            raise SafetyError("empty asset")
        resolved_name = filename or Path(unquote(urlsplit(current).path)).name or "source.html"
        source_extension = extension_from_name(resolved_name)
        detected = detect_mime(raw, source_extension)
        validate_mime(declared_mime, detected, source_extension)
        extension = canonical_extension(detected, source_extension)
        digest = sha256_bytes(raw)
        relative = Path("raw") / "sha256" / digest[:2] / f"{digest}{extension}"
        target = (self._workspace / relative).resolve()
        if self._workspace not in target.parents:
            raise SafetyError("asset path escaped workspace")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() != raw:
                raise StateConflict("existing content-addressed asset differs")
        else:
            descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
            except Exception:
                target.unlink(missing_ok=True)
                raise
        asset_id = f"asset-{digest[:24]}"
        return AssetManifest(
            schema_version=1,
            asset_id=asset_id,
            asset_version=digest,
            parent_document_id=parent_document_id,
            source_url=url,
            source_final_url=current,
            fetched_at_utc=datetime.now(UTC),
            filename=resolved_name,
            source_extension=source_extension,
            extension=extension,
            format_mismatch=source_extension != extension,
            declared_mime=declared_mime,
            detected_mime=detected,
            sha256=digest,
            byte_count=len(raw),
            storage_relative_path=relative.as_posix(),
            official_source_proof=official_source_proof,
        )
