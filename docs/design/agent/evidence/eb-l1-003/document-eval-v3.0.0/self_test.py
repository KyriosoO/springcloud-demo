#!/usr/bin/env python3
"""Exercise the v3 package and report validator with an oracle report and mutations."""

from __future__ import annotations

import copy
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import validate_evaluation_report as validator


PACK_DIR = Path(__file__).resolve().parent


def build_oracle_report(
    manifest: dict[str, Any],
    corpus: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    corpus_by_id = {row["chunk_id"]: row for row in corpus}
    rows: list[dict[str, Any]] = []
    for case in cases:
        accessible_ids = [
            row["chunk_id"] for row in corpus if validator.is_accessible(row, case)
        ]
        relevant = [
            row["chunk_id"]
            for row in sorted(case["relevant_chunks"], key=lambda value: -value["grade"])
            if row["grade"] >= 2 and row["chunk_id"] in accessible_ids
        ]
        if case["answerability"] == "answerable":
            retrieved = relevant + [
                chunk_id for chunk_id in accessible_ids if chunk_id not in relevant
            ][: 50 - len(relevant)]
            citations = [
                chunk_id
                for chunk_id in case["allowed_citations"]
                if chunk_id in corpus_by_id
                and validator.is_accessible(corpus_by_id[chunk_id], case)
            ]
            claims = max(len(case["required_points"]), 1)
            evidence = {
                "factual_claim_count": claims,
                "supported_factual_claim_count": claims,
                "cited_factual_claim_count": claims,
                "valid_direct_citation_count": len(citations),
                "covered_required_point_ids": [
                    point["point_id"] for point in case["required_points"]
                ],
                "evaluator_notes": "synthetic oracle self-test; not a target-system run",
            }
            row = {
                "case_id": case["case_id"],
                "retrieved_chunks": retrieved,
                "model_input_chunks": relevant,
                "answer": case["reference_answer"],
                "citations": citations,
                "refused": False,
                "refusal_reason": None,
                "metric_evidence": evidence,
                "security_events": [],
            }
        else:
            row = {
                "case_id": case["case_id"],
                "retrieved_chunks": [],
                "model_input_chunks": [],
                "answer": case["reference_answer"],
                "citations": [],
                "refused": True,
                "refusal_reason": case["refusal_reason"],
                "metric_evidence": {
                    "factual_claim_count": 0,
                    "supported_factual_claim_count": 0,
                    "cited_factual_claim_count": 0,
                    "valid_direct_citation_count": 0,
                    "covered_required_point_ids": [],
                    "evaluator_notes": "synthetic oracle refusal self-test",
                },
                "security_events": [],
            }
        rows.append(row)

    results_by_id = {row["case_id"]: row for row in rows}
    aggregate = validator.compute_metrics(cases, results_by_id, corpus_by_id)
    strata = validator.build_strata(cases, results_by_id, corpus_by_id)
    failed = validator.failed_gates(aggregate, manifest)
    return {
        "report_version": validator.REPORT_VERSION,
        "dataset_version": validator.DATASET_VERSION,
        "run_id": "v3-validator-oracle-self-test",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "system_under_test": {
            "artifact_version": "synthetic-oracle-not-production",
            "model_version": "synthetic-oracle-not-production",
            "retrieval_config_version": "synthetic-oracle-not-production",
        },
        "aggregate": aggregate,
        "stratified_results": strata,
        "case_results": rows,
        "gate_result": "pass" if not failed else "fail",
        "failed_gates": failed,
        "notes": "Validator self-test only; this is not a target-system quality report.",
    }


def validate_temp(report: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "report.json"
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        return validator.validate_report(PACK_DIR, path)


def main() -> int:
    manifest, corpus, cases, pack_errors = validator.validate_pack(PACK_DIR)
    checks: dict[str, bool] = {"pack_valid": not pack_errors}
    if pack_errors:
        print(json.dumps({"valid": False, "checks": checks, "errors": pack_errors}, indent=2))
        return 1

    oracle = build_oracle_report(manifest, corpus, cases)
    checks["oracle_report_accepted"] = validate_temp(oracle)["valid"]

    duplicate = copy.deepcopy(oracle)
    duplicate["case_results"][-1]["case_id"] = duplicate["case_results"][0]["case_id"]
    checks["duplicate_case_rejected"] = not validate_temp(duplicate)["valid"]

    tampered = copy.deepcopy(oracle)
    tampered["aggregate"]["recall_at_50"] = 0.0
    checks["tampered_aggregate_rejected"] = not validate_temp(tampered)["valid"]

    missing_stratum = copy.deepcopy(oracle)
    del missing_stratum["stratified_results"]["by_tag"]
    checks["missing_stratification_rejected"] = not validate_temp(missing_stratum)["valid"]

    leaked = copy.deepcopy(oracle)
    leaked_row = next(
        row for row in leaked["case_results"] if row["case_id"] == "DOC-EVAL-018"
    )
    leaked_row["retrieved_chunks"] = [corpus[0]["chunk_id"]]
    checks["unreported_access_leak_rejected"] = not validate_temp(leaked)["valid"]

    valid = all(checks.values())
    output = {
        "valid": valid,
        "checks": checks,
        "oracle_gate_result": oracle["gate_result"],
        "oracle_aggregate": oracle["aggregate"],
        "notes": "Oracle report validates the validator only; no target-system run was performed.",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
