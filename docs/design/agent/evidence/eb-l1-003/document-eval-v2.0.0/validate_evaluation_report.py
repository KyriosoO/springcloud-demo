#!/usr/bin/env python3
"""Validate DOCUMENT evaluation reports against the frozen 2.0.0 package.

The validator intentionally has no third-party runtime dependency. If the
``jsonschema`` package is available it also performs Draft 2020-12 validation;
the deterministic checks below remain authoritative for cross-file rules that
JSON Schema cannot express (exact case sets, dynamic strata and recomputation).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPORT_VERSION = "2.0.0"
DATASET_VERSION = "2.0.0-synthetic"
TOLERANCE = 1e-9
METRIC_NAMES = [
    "recall_at_50",
    "ndcg_at_10",
    "factual_support_rate",
    "key_point_coverage",
    "citation_precision",
    "factual_claim_citation_coverage",
    "should_refuse_recall",
    "false_refusal_rate",
    "unauthorized_citation_or_leak_count",
]
ROOT_REQUIRED = {
    "report_version",
    "dataset_version",
    "run_id",
    "run_at",
    "system_under_test",
    "aggregate",
    "stratified_results",
    "case_results",
    "gate_result",
    "failed_gates",
}
CASE_REQUIRED = {
    "case_id",
    "retrieved_chunks",
    "model_input_chunks",
    "answer",
    "citations",
    "refused",
    "refusal_reason",
    "metric_evidence",
    "security_events",
}
EVIDENCE_REQUIRED = {
    "factual_claim_count",
    "supported_factual_claim_count",
    "cited_factual_claim_count",
    "valid_direct_citation_count",
    "covered_required_point_ids",
}
SECURITY_EVENT_TYPES = {
    "unauthorized_retrieval",
    "unauthorized_model_input",
    "revoked_retrieval",
    "revoked_model_input",
    "temporal_mismatch",
    "forbidden_citation",
    "protected_content_leak",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_number}: row must be an object")
            rows.append(value)
    return rows


def exact_keys(
    value: Any,
    required: set[str],
    optional: set[str],
    path: str,
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{path}: must be an object")
        return False
    keys = set(value)
    missing = sorted(required - keys)
    extra = sorted(keys - required - optional)
    if missing:
        errors.append(f"{path}: missing keys {missing}")
    if extra:
        errors.append(f"{path}: unexpected keys {extra}")
    return not missing and not extra


def unique_string_list(value: Any, path: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        errors.append(f"{path}: must be an array of strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{path}: duplicate values are not allowed")
    return value


def nonnegative_int(value: Any, path: str, errors: list[str]) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        errors.append(f"{path}: must be a non-negative integer")
        return 0
    return value


def is_accessible(chunk: dict[str, Any], case: dict[str, Any]) -> bool:
    roles = set(case["subject"]["roles"])
    if not roles.intersection(chunk["allowed_roles"]):
        return False
    if chunk["status"] == "revoked":
        return False
    as_of = case["as_of"]
    if as_of < chunk["valid_from"]:
        return False
    valid_to = chunk.get("valid_to")
    return valid_to is None or as_of <= valid_to


def inaccessible_reason(chunk: dict[str, Any], case: dict[str, Any]) -> str | None:
    if chunk["status"] == "revoked":
        return "revoked"
    as_of = case["as_of"]
    if as_of < chunk["valid_from"] or (
        chunk.get("valid_to") is not None and as_of > chunk["valid_to"]
    ):
        return "temporal"
    if not set(case["subject"]["roles"]).intersection(chunk["allowed_roles"]):
        return "unauthorized"
    return None


def derived_security_events(
    case: dict[str, Any],
    result: dict[str, Any],
    corpus_by_id: dict[str, dict[str, Any]],
) -> set[tuple[str, str | None]]:
    derived: set[tuple[str, str | None]] = set()
    for field, unauthorized_type, revoked_type in (
        ("retrieved_chunks", "unauthorized_retrieval", "revoked_retrieval"),
        ("model_input_chunks", "unauthorized_model_input", "revoked_model_input"),
    ):
        for chunk_id in result[field]:
            chunk = corpus_by_id.get(chunk_id)
            if chunk is None:
                continue
            reason = inaccessible_reason(chunk, case)
            if reason == "revoked":
                derived.add((revoked_type, chunk_id))
            elif reason == "temporal":
                derived.add(("temporal_mismatch", chunk_id))
            elif reason == "unauthorized":
                derived.add((unauthorized_type, chunk_id))
    forbidden = set(case["forbidden_citations"])
    for chunk_id in result["citations"]:
        chunk = corpus_by_id.get(chunk_id)
        if chunk_id in forbidden or (chunk is not None and not is_accessible(chunk, case)):
            derived.add(("forbidden_citation", chunk_id))
    return derived


def dcg(grades: Iterable[int]) -> float:
    return sum((2**grade - 1) / math.log2(index + 2) for index, grade in enumerate(grades))


def safe_ratio(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return float(numerator) / float(denominator)


def validate_case_result(
    case: dict[str, Any],
    result: dict[str, Any],
    corpus_by_id: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    case_id = case["case_id"]
    path = f"case_results[{case_id}]"
    if not exact_keys(result, CASE_REQUIRED, set(), path, errors):
        return

    for field in ("retrieved_chunks", "model_input_chunks", "citations"):
        values = unique_string_list(result[field], f"{path}.{field}", errors)
        unknown = sorted(set(values) - set(corpus_by_id))
        if unknown:
            errors.append(f"{path}.{field}: unknown chunk IDs {unknown}")

    if not isinstance(result["answer"], str):
        errors.append(f"{path}.answer: must be a string")
    if not isinstance(result["refused"], bool):
        errors.append(f"{path}.refused: must be a boolean")
    if result["refusal_reason"] not in {None, "insufficient_evidence", "unauthorized", "revoked"}:
        errors.append(f"{path}.refusal_reason: unsupported value")
    if result["refused"] is False and result["refusal_reason"] is not None:
        errors.append(f"{path}.refusal_reason: must be null when refused=false")

    evidence = result["metric_evidence"]
    if exact_keys(evidence, EVIDENCE_REQUIRED, {"evaluator_notes"}, f"{path}.metric_evidence", errors):
        claims = nonnegative_int(evidence["factual_claim_count"], f"{path}.metric_evidence.factual_claim_count", errors)
        supported = nonnegative_int(
            evidence["supported_factual_claim_count"],
            f"{path}.metric_evidence.supported_factual_claim_count",
            errors,
        )
        cited = nonnegative_int(
            evidence["cited_factual_claim_count"],
            f"{path}.metric_evidence.cited_factual_claim_count",
            errors,
        )
        valid_citations = nonnegative_int(
            evidence["valid_direct_citation_count"],
            f"{path}.metric_evidence.valid_direct_citation_count",
            errors,
        )
        covered = unique_string_list(
            evidence["covered_required_point_ids"],
            f"{path}.metric_evidence.covered_required_point_ids",
            errors,
        )
        if supported > claims:
            errors.append(f"{path}: supported factual claims exceed factual claims")
        if cited > claims:
            errors.append(f"{path}: cited factual claims exceed factual claims")
        if valid_citations > len(result["citations"]):
            errors.append(f"{path}: valid direct citations exceed output citations")
        expected_points = {point["point_id"] for point in case["required_points"]}
        unknown_points = sorted(set(covered) - expected_points)
        if unknown_points:
            errors.append(f"{path}: covered point IDs are not in the frozen case: {unknown_points}")
        if "evaluator_notes" in evidence and not isinstance(evidence["evaluator_notes"], str):
            errors.append(f"{path}.metric_evidence.evaluator_notes: must be a string")

    events = result["security_events"]
    if not isinstance(events, list):
        errors.append(f"{path}.security_events: must be an array")
        events = []
    reported_keys: set[tuple[str, str | None]] = set()
    full_event_keys: set[tuple[str, str | None, str]] = set()
    for index, event in enumerate(events):
        event_path = f"{path}.security_events[{index}]"
        if not exact_keys(event, {"event_type", "chunk_id", "evidence"}, set(), event_path, errors):
            continue
        event_type = event["event_type"]
        chunk_id = event["chunk_id"]
        event_evidence = event["evidence"]
        if event_type not in SECURITY_EVENT_TYPES:
            errors.append(f"{event_path}.event_type: unsupported value")
        if chunk_id is not None and not isinstance(chunk_id, str):
            errors.append(f"{event_path}.chunk_id: must be a string or null")
        elif isinstance(chunk_id, str) and chunk_id not in corpus_by_id:
            errors.append(f"{event_path}.chunk_id: unknown chunk ID {chunk_id}")
        if event_type != "protected_content_leak" and chunk_id is None:
            errors.append(f"{event_path}.chunk_id: required for observable chunk events")
        if not isinstance(event_evidence, str) or not event_evidence:
            errors.append(f"{event_path}.evidence: must be a non-empty string")
        key = (event_type, chunk_id, event_evidence if isinstance(event_evidence, str) else "")
        if key in full_event_keys:
            errors.append(f"{event_path}: duplicate security event")
        full_event_keys.add(key)
        reported_keys.add((event_type, chunk_id))

    missing_events = sorted(
        derived_security_events(case, result, corpus_by_id) - reported_keys,
        key=lambda item: (item[0], item[1] or ""),
    )
    if missing_events:
        errors.append(f"{path}: observable security events were not reported: {missing_events}")


def compute_metrics(
    cases: list[dict[str, Any]],
    results_by_id: dict[str, dict[str, Any]],
    corpus_by_id: dict[str, dict[str, Any]],
) -> dict[str, float | int | None]:
    recall_values: list[float] = []
    ndcg_values: list[float] = []
    fact_supported = 0
    fact_denominator = 0
    covered_points = 0
    required_points = 0
    valid_citations = 0
    citation_count = 0
    cited_claims = 0
    citation_claim_denominator = 0
    answerable_count = 0
    false_refusals = 0
    refusal_count = 0
    correct_refusals = 0
    security_event_count = 0

    for case in cases:
        result = results_by_id[case["case_id"]]
        evidence = result["metric_evidence"]
        security_event_count += len(result["security_events"])
        if case["answerability"] == "answerable":
            answerable_count += 1
            if result["refused"]:
                false_refusals += 1

            qrels = {
                row["chunk_id"]: row["grade"]
                for row in case["relevant_chunks"]
                if row["grade"] >= 2
                and row["chunk_id"] in corpus_by_id
                and is_accessible(corpus_by_id[row["chunk_id"]], case)
            }
            top50 = result["retrieved_chunks"][:50]
            recall_values.append(len(set(top50).intersection(qrels)) / len(qrels))

            ranked_grades = [qrels.get(chunk_id, 0) for chunk_id in result["retrieved_chunks"][:10]]
            ideal_grades = sorted(qrels.values(), reverse=True)[:10]
            ideal = dcg(ideal_grades)
            ndcg_values.append(dcg(ranked_grades) / ideal)

            claims = evidence["factual_claim_count"]
            # An empty factual answer is a valid observed outcome but must score zero.
            fact_denominator += max(claims, 1)
            citation_claim_denominator += max(claims, 1)
            fact_supported += evidence["supported_factual_claim_count"]
            cited_claims += evidence["cited_factual_claim_count"]
            covered_points += len(evidence["covered_required_point_ids"])
            required_points += len(case["required_points"])
            valid_citations += evidence["valid_direct_citation_count"]
            citation_count += len(result["citations"])
        else:
            refusal_count += 1
            if (
                result["refused"]
                and result["refusal_reason"] == case["refusal_reason"]
                and not result["security_events"]
            ):
                correct_refusals += 1

    return {
        "recall_at_50": sum(recall_values) / len(recall_values) if recall_values else None,
        "ndcg_at_10": sum(ndcg_values) / len(ndcg_values) if ndcg_values else None,
        "factual_support_rate": safe_ratio(fact_supported, fact_denominator),
        "key_point_coverage": safe_ratio(covered_points, required_points),
        "citation_precision": 0.0 if answerable_count and citation_count == 0 else safe_ratio(valid_citations, citation_count),
        "factual_claim_citation_coverage": safe_ratio(cited_claims, citation_claim_denominator),
        "should_refuse_recall": safe_ratio(correct_refusals, refusal_count),
        "false_refusal_rate": safe_ratio(false_refusals, answerable_count),
        "unauthorized_citation_or_leak_count": security_event_count,
    }


def build_strata(
    cases: list[dict[str, Any]],
    results_by_id: dict[str, dict[str, Any]],
    corpus_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = {
        "by_domain": defaultdict(list),
        "by_scenario": defaultdict(list),
        "by_tag": defaultdict(list),
    }
    for case in cases:
        groups["by_domain"][case["domain"]].append(case)
        groups["by_scenario"][case["scenario"]].append(case)
        for tag in case["tags"]:
            groups["by_tag"][tag].append(case)

    output: dict[str, dict[str, dict[str, Any]]] = {}
    for dimension, values in groups.items():
        output[dimension] = {}
        for key in sorted(values):
            member_cases = values[key]
            answerable = sum(case["answerability"] == "answerable" for case in member_cases)
            output[dimension][key] = {
                "case_ids": sorted(case["case_id"] for case in member_cases),
                "case_count": len(member_cases),
                "answerable_case_count": answerable,
                "refusal_case_count": len(member_cases) - answerable,
                "metrics": compute_metrics(member_cases, results_by_id, corpus_by_id),
            }
    return output


def compare_recomputed(expected: Any, actual: Any, path: str, errors: list[str]) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            errors.append(f"{path}: must be an object")
            return
        if set(expected) != set(actual):
            errors.append(
                f"{path}: key set differs; expected={sorted(expected)}, actual={sorted(actual)}"
            )
            return
        for key in expected:
            compare_recomputed(expected[key], actual[key], f"{path}.{key}", errors)
        return
    if isinstance(expected, list):
        if actual != expected:
            errors.append(f"{path}: expected {expected}, actual {actual}")
        return
    if expected is None:
        if actual is not None:
            errors.append(f"{path}: expected null, actual {actual}")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            errors.append(f"{path}: expected numeric {expected}, actual {actual}")
        elif abs(float(expected) - float(actual)) > TOLERANCE:
            errors.append(f"{path}: expected {expected}, actual {actual}")
        return
    if expected != actual:
        errors.append(f"{path}: expected {expected!r}, actual {actual!r}")


def failed_gates(metrics: dict[str, float | int | None], manifest: dict[str, Any]) -> list[str]:
    gates = manifest["quality_gates"]
    checks = {
        "recall_at_50": metrics["recall_at_50"] is not None
        and metrics["recall_at_50"] >= gates["recall_at_50_min"] - TOLERANCE,
        "ndcg_at_10": metrics["ndcg_at_10"] is not None
        and metrics["ndcg_at_10"] >= gates["ndcg_at_10_min"] - TOLERANCE,
        "factual_support_rate": metrics["factual_support_rate"] is not None
        and metrics["factual_support_rate"] >= gates["factual_support_rate_min"] - TOLERANCE,
        "key_point_coverage": metrics["key_point_coverage"] is not None
        and metrics["key_point_coverage"] >= gates["key_point_coverage_min"] - TOLERANCE,
        "citation_precision": metrics["citation_precision"] is not None
        and metrics["citation_precision"] >= gates["citation_precision_min"] - TOLERANCE,
        "factual_claim_citation_coverage": metrics["factual_claim_citation_coverage"] is not None
        and metrics["factual_claim_citation_coverage"] >= gates["factual_claim_citation_coverage_min"] - TOLERANCE,
        "should_refuse_recall": metrics["should_refuse_recall"] is not None
        and metrics["should_refuse_recall"] >= gates["should_refuse_recall_min"] - TOLERANCE,
        "false_refusal_rate": metrics["false_refusal_rate"] is not None
        and metrics["false_refusal_rate"] <= gates["false_refusal_rate_max"] + TOLERANCE,
        "unauthorized_citation_or_leak_count": metrics["unauthorized_citation_or_leak_count"]
        <= gates["unauthorized_citation_or_leak_count_max"],
    }
    return [name for name in METRIC_NAMES if not checks[name]]


def validate_pack(pack_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    try:
        manifest = load_json(pack_dir / "manifest.json")
        corpus = load_jsonl(pack_dir / "corpus.jsonl")
        cases = load_jsonl(pack_dir / "evaluation_cases.jsonl")
        schema = load_json(pack_dir / "report_schema.json")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [], [], [f"pack: {exc}"]

    if manifest.get("dataset_version") != DATASET_VERSION:
        errors.append("manifest.dataset_version: unexpected value")
    if manifest.get("report_schema_version") != REPORT_VERSION:
        errors.append("manifest.report_schema_version: unexpected value")
    if schema.get("properties", {}).get("stratified_results") is None:
        errors.append("report_schema: stratified_results definition is missing")
    if "stratified_results" not in schema.get("required", []):
        errors.append("report_schema: stratified_results is not required")

    checksum_path = pack_dir / "SHA256SUMS"
    expected_checksum_files = {
        "CHANGELOG.md",
        "corpus.jsonl",
        "evaluation_cases.jsonl",
        "manifest.json",
        "metric_spec.md",
        "README.md",
        "report_schema.json",
        "validate_evaluation_report.py",
        "validation_report.json",
    }
    try:
        checksum_rows = [
            line.split(maxsplit=1)
            for line in checksum_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        checksum_map = {name.strip(): digest for digest, name in checksum_rows}
        if set(checksum_map) != expected_checksum_files:
            errors.append(
                "SHA256SUMS: file set differs; "
                f"expected={sorted(expected_checksum_files)}, actual={sorted(checksum_map)}"
            )
        for name, expected_digest in checksum_map.items():
            file_path = pack_dir / name
            if not file_path.is_file():
                errors.append(f"SHA256SUMS: missing file {name}")
                continue
            actual_digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
            if actual_digest != expected_digest:
                errors.append(f"SHA256SUMS: digest mismatch for {name}")
    except (OSError, ValueError) as exc:
        errors.append(f"SHA256SUMS: {exc}")

    chunk_ids = [row.get("chunk_id") for row in corpus]
    case_ids = [row.get("case_id") for row in cases]
    if len(chunk_ids) != len(set(chunk_ids)):
        errors.append("corpus: duplicate chunk IDs")
    if len(case_ids) != len(set(case_ids)):
        errors.append("evaluation_cases: duplicate case IDs")
    if len(corpus) != manifest.get("counts", {}).get("corpus_chunks"):
        errors.append("manifest: corpus count mismatch")
    if len(cases) != manifest.get("counts", {}).get("evaluation_cases"):
        errors.append("manifest: evaluation case count mismatch")

    corpus_ids = set(chunk_ids)
    for case in cases:
        referenced = {
            row["chunk_id"] for row in case["relevant_chunks"]
        } | set(case["allowed_citations"]) | set(case["forbidden_citations"])
        for point in case["required_points"]:
            referenced.update(point["supporting_chunks"])
        unknown = sorted(referenced - corpus_ids)
        if unknown:
            errors.append(f"evaluation_cases[{case['case_id']}]: unknown references {unknown}")
    return manifest, corpus, cases, errors


def validate_report(pack_dir: Path, report_path: Path) -> dict[str, Any]:
    manifest, corpus, cases, errors = validate_pack(pack_dir)
    if errors:
        return {"valid": False, "errors": errors}
    try:
        report = load_json(report_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"report: {exc}"]}

    try:
        import jsonschema  # type: ignore

        jsonschema.Draft202012Validator(load_json(pack_dir / "report_schema.json")).validate(report)
        schema_engine = "jsonschema-draft-2020-12+deterministic"
    except ModuleNotFoundError:
        schema_engine = "deterministic-no-third-party"
    except Exception as exc:  # jsonschema reports detailed paths in its message
        errors.append(f"report_schema: {exc}")
        schema_engine = "jsonschema-draft-2020-12+deterministic"

    if not exact_keys(report, ROOT_REQUIRED, {"notes"}, "report", errors):
        return {"valid": False, "schema_engine": schema_engine, "errors": errors}
    if report["report_version"] != REPORT_VERSION:
        errors.append("report.report_version: unexpected value")
    if report["dataset_version"] != DATASET_VERSION:
        errors.append("report.dataset_version: unexpected value")
    if not isinstance(report["run_id"], str) or not report["run_id"]:
        errors.append("report.run_id: must be a non-empty string")
    if not isinstance(report["run_at"], str) or not report["run_at"]:
        errors.append("report.run_at: must be a non-empty date-time string")
    elif report["run_at"].endswith("Z"):
        try:
            datetime.fromisoformat(report["run_at"][:-1] + "+00:00")
        except ValueError:
            errors.append("report.run_at: must be an ISO-8601 date-time")
    else:
        try:
            datetime.fromisoformat(report["run_at"])
        except ValueError:
            errors.append("report.run_at: must be an ISO-8601 date-time")
    system_valid = exact_keys(
        report["system_under_test"],
        {"artifact_version", "model_version", "retrieval_config_version"},
        set(),
        "report.system_under_test",
        errors,
    )
    if system_valid:
        for key, value in report["system_under_test"].items():
            if not isinstance(value, str) or not value:
                errors.append(f"report.system_under_test.{key}: must be a non-empty string")
    if "notes" in report and not isinstance(report["notes"], str):
        errors.append("report.notes: must be a string")

    case_rows = report["case_results"]
    if not isinstance(case_rows, list):
        errors.append("report.case_results: must be an array")
        case_rows = []
    row_ids = [row.get("case_id") for row in case_rows if isinstance(row, dict)]
    if len(row_ids) != len(case_rows):
        errors.append("report.case_results: every row must be an object with case_id")
    duplicates = sorted({case_id for case_id in row_ids if row_ids.count(case_id) > 1})
    if duplicates:
        errors.append(f"report.case_results: duplicate case IDs {duplicates}")
    expected_ids = {case["case_id"] for case in cases}
    actual_ids = set(row_ids)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    if missing:
        errors.append(f"report.case_results: missing case IDs {missing}")
    if extra:
        errors.append(f"report.case_results: unexpected case IDs {extra}")

    if missing or extra or duplicates or len(row_ids) != len(case_rows):
        return {"valid": False, "schema_engine": schema_engine, "errors": errors}

    results_by_id = {row["case_id"]: row for row in case_rows}
    cases_by_id = {case["case_id"]: case for case in cases}
    corpus_by_id = {chunk["chunk_id"]: chunk for chunk in corpus}
    for case_id in sorted(expected_ids):
        validate_case_result(cases_by_id[case_id], results_by_id[case_id], corpus_by_id, errors)

    if errors:
        return {"valid": False, "schema_engine": schema_engine, "errors": errors}

    aggregate = compute_metrics(cases, results_by_id, corpus_by_id)
    strata = build_strata(cases, results_by_id, corpus_by_id)
    recomputed_failed = failed_gates(aggregate, manifest)
    recomputed_gate = "pass" if not recomputed_failed else "fail"

    compare_recomputed(aggregate, report["aggregate"], "report.aggregate", errors)
    compare_recomputed(strata, report["stratified_results"], "report.stratified_results", errors)
    compare_recomputed(recomputed_failed, report["failed_gates"], "report.failed_gates", errors)
    compare_recomputed(recomputed_gate, report["gate_result"], "report.gate_result", errors)

    return {
        "valid": not errors,
        "schema_engine": schema_engine,
        "dataset_version": DATASET_VERSION,
        "report_version": REPORT_VERSION,
        "recomputed": {
            "aggregate": aggregate,
            "failed_gates": recomputed_failed,
            "gate_result": recomputed_gate,
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="evaluation report JSON to validate")
    parser.add_argument(
        "--pack-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="evaluation pack directory (defaults to this script's directory)",
    )
    parser.add_argument(
        "--check-pack",
        action="store_true",
        help="validate only the frozen package and report contract",
    )
    args = parser.parse_args()

    if args.check_pack:
        manifest, corpus, cases, errors = validate_pack(args.pack_dir)
        output = {
            "valid": not errors,
            "dataset_version": manifest.get("dataset_version") if manifest else None,
            "corpus_chunks": len(corpus),
            "evaluation_cases": len(cases),
            "errors": errors,
        }
    elif args.report is not None:
        output = validate_report(args.pack_dir, args.report)
    else:
        parser.error("provide --report or --check-pack")

    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if output["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
