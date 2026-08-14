from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final, NoReturn


SCHEMA_VERSION: Final = 1
WORK_PACKAGE_ID: Final = "WP-EMP-EGRESS-WORK-BASE-DIAG-01"
RUN_ID: Final = "employee-work-base-static-diagnostic-v1-20260814-run-01"
SOURCE_EVIDENCE_PATH: Final = (
    "agent-runtime/tests/integration/adapters/employee/evidence/"
    "employee-egress-input-qualification-diagnostic-v2-20260814-run-01.json"
)
SOURCE_EVIDENCE_SHA256: Final = (
    "f23115069adaa0bfedcfdb01b7f0889acb079961319db3c44547549ca088c46f"
)

SOURCE_FILES: Final[tuple[tuple[str, str], ...]] = (
    (
        "employee-service/src/main/java/com/dylan/employee/model/Employee.java",
        "680238f6773c28e9d830503441be4e069c2f2f70ba4bedb1d32f5a1046abd5b7",
    ),
    (
        "employee-service/src/main/java/com/dylan/employee/mapper/EmployeeMapper.java",
        "a8296dc6ebbb8763dd6b7972f350ae4aea78a3cb3780ec0057f481a89471c4dc",
    ),
    (
        "employee-service/src/main/java/com/dylan/employee/mapper/EmployeeSqlProvider.java",
        "372cae00185752cc57ad3409453cfc2522b05ab2a832b05f7938584a502aaa68",
    ),
    (
        "employee-service/src/main/java/com/dylan/employee/service/EmployeeService.java",
        "350484f3fd5f9a9085759a671d5112a822a4cc7956e608d4d2b85326a1a17bf2",
    ),
    (
        "employee-service/src/main/java/com/dylan/employee/controller/EmployeeController.java",
        "75aa9c2eff20f42790b605f811efe41a7352cd7441bb9a90911d03142d88cf3a",
    ),
    (
        "employee-service/src/main/resources/static/employee-workflow.html",
        "844b4c362878f0d2a4acfa1ad241e665201ddfa7f0e58dc45359aea505bbebd3",
    ),
    (
        "employee-service/README.md",
        "1956d3a31338ace3602b9f11bbdd8c6e592381322b9972a3c16106ebd719aec8",
    ),
    (
        "scripts/migration/off-03a-employee-index-rebuild.ps1",
        "1be57cc0f84e04fea28c0973a1e79da5aef1479444833b514c5cc9dffff18632",
    ),
    (
        "employee-service/src/test/java/com/dylan/employee/live/"
        "EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest.java",
        "564f71c0ffa76223db8dac3da755e9a7650513c8dda54eee0a4205215f89e6da",
    ),
)

_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "schemaVersion",
        "workPackageId",
        "runId",
        "recordedAt",
        "status",
        "sourceEvidence",
        "sourceFiles",
        "mapping",
        "writeSources",
        "repositoryAssets",
        "diagnosis",
        "safety",
    }
)
_SOURCE_EVIDENCE_KEYS: Final = frozenset(
    {"path", "sha256", "totalRows", "workBaseSiValidRows"}
)
_SOURCE_FILE_KEYS: Final = frozenset({"path", "sha256"})
_MAPPING_KEYS: Final = frozenset(
    {
        "entityProperty",
        "entityGetter",
        "entitySetter",
        "resultMap",
        "selectColumn",
        "insertColumn",
        "updateColumn",
        "priorAggregateDirectColumn",
    }
)
_WRITE_SOURCE_KEYS: Final = frozenset(
    {
        "controllerUsesMapPayload",
        "serviceUsesMapPayload",
        "insertWritesOnlyPresentKey",
        "updateWritesOnlyPresentKey",
        "typedWriteRequestDto",
        "workBaseRequiredValidation",
        "workBaseDefaulting",
        "workBaseBackfill",
        "esRebuildIsDownstream",
    }
)
_ASSET_KEYS: Final = frozenset(
    {
        "employeeDdlAssets",
        "employeeDataAssets",
        "employeeInitializationComponents",
        "employeeImportComponents",
        "employeeBackfillComponents",
    }
)
_DIAGNOSIS_KEYS: Final = frozenset(
    {
        "reason",
        "readMappingCauseExcluded",
        "physicalColumnDefinition",
        "rawValueDistribution",
        "confidence",
        "nextStep",
    }
)
_SAFETY_KEYS: Final = frozenset(
    {
        "databaseQueries",
        "employeeEndpointCalls",
        "serviceStarts",
        "modelCalls",
        "jwtRead",
        "llmApiKeyRead",
        "identifiersPersisted",
        "fieldValuesPersisted",
    }
)


class WorkBaseStaticDiagnosticError(ValueError):
    pass


def _invalid() -> NoReturn:
    raise WorkBaseStaticDiagnosticError("employee.work_base_static_diagnostic_invalid")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            _invalid()
        value[key] = item
    return value


def load_strict_json(path: Path, *, max_bytes: int = 131_072) -> dict[str, Any]:
    raw = path.read_bytes()
    if not raw or len(raw) > max_bytes or raw.startswith(b"\xef\xbb\xbf"):
        _invalid()
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError):
        _invalid()
    if type(value) is not dict:
        _invalid()
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_mapping(value: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        _invalid()
    return value


def _require_zero(value: object) -> None:
    if type(value) is not int or value != 0:
        _invalid()


def _is_utc_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _expected_source_files() -> list[dict[str, str]]:
    return [{"path": path, "sha256": digest} for path, digest in SOURCE_FILES]


def validate_repository_snapshot(repository_root: Path) -> None:
    source_evidence = repository_root / SOURCE_EVIDENCE_PATH
    if (
        not source_evidence.is_file()
        or sha256_file(source_evidence) != SOURCE_EVIDENCE_SHA256
    ):
        _invalid()
    for relative_path, expected_sha256 in SOURCE_FILES:
        path = repository_root / relative_path
        if not path.is_file() or sha256_file(path) != expected_sha256:
            _invalid()


def _employee_asset_counts(repository_root: Path) -> dict[str, int]:
    excluded = {
        ".git",
        ".idea",
        ".codex-live",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "docs",
        "node_modules",
        "target",
        "tests",
    }
    text_suffixes = {
        ".csv",
        ".ddl",
        ".java",
        ".json",
        ".jsonl",
        ".properties",
        ".ps1",
        ".py",
        ".sh",
        ".sql",
        ".tsv",
        ".xml",
        ".yaml",
        ".yml",
    }
    files = [
        path
        for path in repository_root.rglob("*")
        if path.is_file()
        and not any(part.lower() in excluded for part in path.relative_to(repository_root).parts)
    ]

    def text_of(path: Path) -> str:
        if path.suffix.lower() not in text_suffixes:
            return ""
        return path.read_text(encoding="utf-8", errors="strict").lower()

    contents = {path: text_of(path) for path in files}

    def employee_scoped(path: Path) -> bool:
        relative = path.relative_to(repository_root).as_posix().lower()
        content = contents[path]
        return "employee" in relative or "employee" in content

    ddl_assets = [
        path
        for path in files
        if path.suffix.lower() in {".sql", ".ddl"} and employee_scoped(path)
    ]
    data_assets = [
        path
        for path in files
        if path.suffix.lower() in {".csv", ".tsv", ".xls", ".xlsx", ".jsonl"}
        and employee_scoped(path)
    ]

    def named_components(
        *, name_tokens: tuple[str, ...], content_tokens: tuple[str, ...]
    ) -> int:
        return sum(
            1
            for path in files
            if employee_scoped(path)
            and (
                any(token in path.name.lower() for token in name_tokens)
                or any(token in contents[path] for token in content_tokens)
            )
        )

    return {
        "employeeDdlAssets": len(ddl_assets),
        "employeeDataAssets": len(data_assets),
        "employeeInitializationComponents": named_components(
            name_tokens=("initializer", "bootstrap", "seed"),
            content_tokens=(
                "commandlinerunner",
                "applicationrunner",
                "spring.sql.init",
            ),
        ),
        "employeeImportComponents": named_components(
            name_tokens=("importer", "loader"),
            content_tokens=("load data", "copy employee", "employee import"),
        ),
        "employeeBackfillComponents": named_components(
            name_tokens=("backfill",), content_tokens=("backfill",)
        ),
    }


def inspect_repository(repository_root: Path) -> dict[str, object]:
    validate_repository_snapshot(repository_root)
    employee = (repository_root / SOURCE_FILES[0][0]).read_text(encoding="utf-8")
    mapper = (repository_root / SOURCE_FILES[1][0]).read_text(encoding="utf-8")
    sql_provider = (repository_root / SOURCE_FILES[2][0]).read_text(encoding="utf-8")
    service = (repository_root / SOURCE_FILES[3][0]).read_text(encoding="utf-8")
    controller = (repository_root / SOURCE_FILES[4][0]).read_text(encoding="utf-8")
    workflow_ui = (repository_root / SOURCE_FILES[5][0]).read_text(encoding="utf-8")
    readme = (repository_root / SOURCE_FILES[6][0]).read_text(encoding="utf-8")
    es_rebuild = (repository_root / SOURCE_FILES[7][0]).read_text(encoding="utf-8")
    aggregate_test = (repository_root / SOURCE_FILES[8][0]).read_text(encoding="utf-8")

    mapping = {
        "entityProperty": "private String workBaseSi;" in employee,
        "entityGetter": "String getWorkBaseSi()" in employee,
        "entitySetter": "void setWorkBaseSi(String workBaseSi)" in employee,
        "resultMap": (
            '@Result(property = "workBaseSi", column = "WORK_BASE_SI")' in mapper
        ),
        "selectColumn": (
            '"WORK_BASE_SI", "WORK_BASE_AF"' in sql_provider
            and 'return "SELECT " + columnList()' in sql_provider
        ),
        "insertColumn": (
            "public String insert(Map<String, Object> employee)" in sql_provider
            and "if (hasField(employee, i))" in sql_provider
        ),
        "updateColumn": (
            "public String updateByIdCardNo(Map<String, Object> employee)" in sql_provider
            and sql_provider.count("if (hasField(employee, i))") == 2
        ),
        "priorAggregateDirectColumn": (
            "SUM(CASE WHEN" in aggregate_test
            and "WORK_BASE_SI" in aggregate_test
            and "jdbcTemplate.queryForMap(" in aggregate_test
        ),
    }
    if any(value is not True for value in mapping.values()):
        _invalid()

    write_sources = {
        "controllerUsesMapPayload": (
            controller.count("@RequestBody Map<String, Object> employee") == 2
        ),
        "serviceUsesMapPayload": (
            "create(Map<String, Object> employee" in service
            and "update(String idCardNo, Map<String, Object> submitted" in service
        ),
        "insertWritesOnlyPresentKey": "private boolean hasField(" in sql_provider,
        "updateWritesOnlyPresentKey": "employee.containsKey(PROPERTIES[index])" in sql_provider,
        "typedWriteRequestDto": False,
        "workBaseRequiredValidation": False,
        "workBaseDefaulting": False,
        "workBaseBackfill": False,
        "esRebuildIsDownstream": (
            "workBaseSi" in es_rebuild
            and "rebuild" in es_rebuild.lower()
            and 'document.put("workBaseSi", employee.getWorkBaseSi())' in service
        ),
    }
    if any(
        write_sources[key] is not expected
        for key, expected in {
            "controllerUsesMapPayload": True,
            "serviceUsesMapPayload": True,
            "insertWritesOnlyPresentKey": True,
            "updateWritesOnlyPresentKey": True,
            "typedWriteRequestDto": False,
            "workBaseRequiredValidation": False,
            "workBaseDefaulting": False,
            "workBaseBackfill": False,
            "esRebuildIsDownstream": True,
        }.items()
    ):
        _invalid()
    if "workBaseSi" in workflow_ui or "workBaseSi" in readme:
        _invalid()

    assets = _employee_asset_counts(repository_root)
    if any(value != 0 for value in assets.values()):
        _invalid()
    return {
        "mapping": mapping,
        "writeSources": write_sources,
        "repositoryAssets": assets,
    }


def validate_evidence(value: Mapping[str, object]) -> None:
    top = _require_mapping(value, _TOP_LEVEL_KEYS)
    if (
        top["schemaVersion"] != SCHEMA_VERSION
        or top["workPackageId"] != WORK_PACKAGE_ID
        or top["runId"] != RUN_ID
        or top["status"] != "completed_with_static_limit"
        or not _is_utc_timestamp(top["recordedAt"])
    ):
        _invalid()

    source = _require_mapping(top["sourceEvidence"], _SOURCE_EVIDENCE_KEYS)
    if source != {
        "path": SOURCE_EVIDENCE_PATH,
        "sha256": SOURCE_EVIDENCE_SHA256,
        "totalRows": 990,
        "workBaseSiValidRows": 0,
    }:
        _invalid()

    source_files = top["sourceFiles"]
    if source_files != _expected_source_files():
        _invalid()
    if not isinstance(source_files, list):
        _invalid()
    for item in source_files:
        _require_mapping(item, _SOURCE_FILE_KEYS)

    mapping = _require_mapping(top["mapping"], _MAPPING_KEYS)
    if any(value is not True for value in mapping.values()):
        _invalid()

    writes = _require_mapping(top["writeSources"], _WRITE_SOURCE_KEYS)
    expected_writes: Mapping[str, object] = {
        "controllerUsesMapPayload": True,
        "serviceUsesMapPayload": True,
        "insertWritesOnlyPresentKey": True,
        "updateWritesOnlyPresentKey": True,
        "typedWriteRequestDto": False,
        "workBaseRequiredValidation": False,
        "workBaseDefaulting": False,
        "workBaseBackfill": False,
        "esRebuildIsDownstream": True,
    }
    if writes != expected_writes:
        _invalid()

    assets = _require_mapping(top["repositoryAssets"], _ASSET_KEYS)
    for item in assets.values():
        _require_zero(item)

    diagnosis = _require_mapping(top["diagnosis"], _DIAGNOSIS_KEYS)
    if diagnosis != {
        "reason": "data_population_provenance_gap",
        "readMappingCauseExcluded": True,
        "physicalColumnDefinition": "not_versioned",
        "rawValueDistribution": "not_observable_without_separate_query",
        "confidence": "strong_static_mapping_limited_physical_state",
        "nextStep": "separate_metadata_and_aggregate_authorization_required",
    }:
        _invalid()

    safety = _require_mapping(top["safety"], _SAFETY_KEYS)
    expected_safety: Mapping[str, object] = {
        "databaseQueries": 0,
        "employeeEndpointCalls": 0,
        "serviceStarts": 0,
        "modelCalls": 0,
        "jwtRead": False,
        "llmApiKeyRead": False,
        "identifiersPersisted": False,
        "fieldValuesPersisted": False,
    }
    if safety != expected_safety:
        _invalid()


def build_evidence(
    repository_root: Path,
    *,
    recorded_at: str,
) -> dict[str, object]:
    inspection = inspect_repository(repository_root)
    evidence: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "workPackageId": WORK_PACKAGE_ID,
        "runId": RUN_ID,
        "recordedAt": recorded_at,
        "status": "completed_with_static_limit",
        "sourceEvidence": {
            "path": SOURCE_EVIDENCE_PATH,
            "sha256": SOURCE_EVIDENCE_SHA256,
            "totalRows": 990,
            "workBaseSiValidRows": 0,
        },
        "sourceFiles": _expected_source_files(),
        "mapping": inspection["mapping"],
        "writeSources": inspection["writeSources"],
        "repositoryAssets": inspection["repositoryAssets"],
        "diagnosis": {
            "reason": "data_population_provenance_gap",
            "readMappingCauseExcluded": True,
            "physicalColumnDefinition": "not_versioned",
            "rawValueDistribution": "not_observable_without_separate_query",
            "confidence": "strong_static_mapping_limited_physical_state",
            "nextStep": "separate_metadata_and_aggregate_authorization_required",
        },
        "safety": {
            "databaseQueries": 0,
            "employeeEndpointCalls": 0,
            "serviceStarts": 0,
            "modelCalls": 0,
            "jwtRead": False,
            "llmApiKeyRead": False,
            "identifiersPersisted": False,
            "fieldValuesPersisted": False,
        },
    }
    validate_evidence(evidence)
    return evidence
