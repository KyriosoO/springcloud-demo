from __future__ import annotations

import ipaddress
import posixpath
import re
import zipfile
from pathlib import PurePosixPath
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .errors import SafetyError

ALLOWED_SCHEMES = frozenset({"https"})
ALLOWED_EXTENSIONS = frozenset({".html", ".htm", ".pdf", ".doc", ".docx", ".xls", ".xlsx"})
MIME_BY_EXTENSION = {
    ".html": frozenset({"text/html", "application/xhtml+xml"}),
    ".htm": frozenset({"text/html", "application/xhtml+xml"}),
    ".pdf": frozenset({"application/pdf"}),
    ".doc": frozenset({"application/msword", "application/octet-stream"}),
    ".docx": frozenset({"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"}),
    ".xls": frozenset({"application/vnd.ms-excel", "application/octet-stream"}),
    ".xlsx": frozenset({"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip", "application/octet-stream"}),
}


def normalize_official_url(url: str, allowed_hosts: frozenset[str]) -> str:
    if len(url) > 4096 or "\x00" in url:
        raise SafetyError("invalid URL length or NUL")
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SafetyError("only HTTPS official sources are allowed")
    if parsed.username or parsed.password or parsed.fragment:
        raise SafetyError("URL credentials and fragments are forbidden")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise SafetyError("URL host is required")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise SafetyError("IP literal is forbidden")
    if host not in allowed_hosts:
        raise SafetyError(f"host is not allowlisted: {host}")
    if parsed.port not in (None, 443):
        raise SafetyError("non-standard port is forbidden")
    normalized_path = posixpath.normpath(parsed.path or "/")
    if not normalized_path.startswith("/") or "/../" in f"{normalized_path}/":
        raise SafetyError("invalid URL path")
    return urlunsplit(SplitResult("https", host, normalized_path, parsed.query, ""))


def extension_from_name(name: str) -> str:
    match = re.search(r"(\.[A-Za-z0-9]+)$", name)
    extension = match.group(1).lower() if match else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise SafetyError(f"unsupported extension: {extension or '<none>'}")
    return extension


def detect_mime(raw: bytes, extension: str) -> str:
    if extension in {".html", ".htm"}:
        prefix = raw[:1024].lstrip().lower()
        if b"<html" in prefix or b"<!doctype html" in prefix:
            return "text/html"
    if raw.startswith(b"%PDF-"):
        return "application/pdf"
    if raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword" if extension in {".doc", ".docx"} else "application/vnd.ms-excel"
    if raw.startswith(b"PK\x03\x04"):
        if extension == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if extension == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    raise SafetyError("file signature does not match an allowed type")


def validate_mime(declared: str | None, detected: str, extension: str) -> None:
    documented_legacy_office_mismatch = (
        extension == ".docx"
        and detected == "application/msword"
        and declared is not None
        and declared.split(";", 1)[0].strip().lower()
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    if detected not in MIME_BY_EXTENSION[extension] and not documented_legacy_office_mismatch:
        raise SafetyError("detected MIME does not match extension")
    if declared:
        normalized = declared.split(";", 1)[0].strip().lower()
        if normalized not in MIME_BY_EXTENSION[extension]:
            raise SafetyError("declared MIME does not match extension")


def canonical_extension(detected_mime: str, source_extension: str) -> str:
    if detected_mime == "application/msword":
        return ".doc"
    if detected_mime == "application/vnd.ms-excel":
        return ".xls"
    return source_extension


def validate_zip_container(
    archive: zipfile.ZipFile,
    *,
    max_entries: int = 1000,
    max_total_uncompressed: int = 100 * 1024 * 1024,
    max_single_uncompressed: int = 50 * 1024 * 1024,
    max_ratio: float = 100.0,
) -> None:
    infos = archive.infolist()
    if len(infos) > max_entries:
        raise SafetyError("archive entry limit exceeded")
    seen: set[str] = set()
    total = 0
    for info in infos:
        path = PurePosixPath(info.filename.replace("\\", "/"))
        normalized = str(path)
        if path.is_absolute() or ".." in path.parts or re.match(r"^[A-Za-z]:", normalized):
            raise SafetyError("archive path traversal")
        folded = normalized.casefold()
        if folded in seen:
            raise SafetyError("duplicate normalized archive path")
        seen.add(folded)
        if info.flag_bits & 0x1:
            raise SafetyError("encrypted archive entry")
        if info.file_size > max_single_uncompressed:
            raise SafetyError("archive member size limit exceeded")
        total += info.file_size
        if total > max_total_uncompressed:
            raise SafetyError("archive total size limit exceeded")
        if info.compress_size == 0 and info.file_size > 0:
            raise SafetyError("invalid compression ratio")
        if info.compress_size and info.file_size / info.compress_size > max_ratio:
            raise SafetyError("archive compression ratio limit exceeded")
