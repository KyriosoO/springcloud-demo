from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_runtime.knowledge.evidence.summary_task_v4 import SUMMARY_PROMPT_V4
from tests.evaluation.knowledge.live_bootstrap import _candidate_id, _unexpected_live_worktree_entries
from tests.evaluation.knowledge.live_contracts import (
    LiveAuthorizationRecord,
    LiveAuthorizationTemplate,
    LiveP5Manifest,
    load_manifest,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SUMMARY_PROMPT_V4_SHA256 = hashlib.sha256(SUMMARY_PROMPT_V4.encode("utf-8")).hexdigest()


def _manifest_payload() -> dict[str, object]:
    return {
        "schemaVersion": 4,
        "status": "prepared_unconsumed",
        "workPackageId": "WP-K-EFFECT-LIVE-06",
        "runId": "knowledge-p5-live-v3-20260828-candidate-06",
        "authorizationReference": "P3_00:GATE-077",
        "datasetPath": "agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl",
        "datasetSha256": "1ea7417d80686545bd96d0f88f27b5b57de3de2ae6d6cb60c272190193645408",
        "datasetCaseCount": 26,
        "evaluationVariants": ["primary", "rewrite_ablation"],
        "principalProfileId": "tax-knowledge-admin-reader-v1",
        "readAuthorizationEvidenceRef": "WP-KRET-REAL-01:authorizationMatrix.admin",
        "gateEvidence": [
            {"gateId": "SA-GATE-002", "evidenceRef": "P3_00:GATE-020"},
            {"gateId": "CR-GATE-003", "evidenceRef": "P3_00:CR-GATE-003"},
            {"gateId": "SA-GATE-003", "evidenceRef": "P3_00:GATE-029"},
            {"gateId": "SA-GATE-006", "evidenceRef": "P3_00:GATE-032"},
        ],
        "paidRequestBudget": {
            "capabilityExecutions": 52,
            "knowledgeRewrite": 26,
            "knowledgeSummary": 52,
            "coreAnswer": 0,
            "retry": 0,
            "maximumPaidRequests": 78,
        },
        "providerMode": "live",
        "modelName": "deepseek-v4-pro",
        "taskVersions": {"knowledge_rewrite": "1", "knowledge_summary": "4"},
        "configurationBinding": {
            "domainCatalogVersion": "tax-domain-catalog-v2",
            "flowConfigVersion": "knowledge-flow-config-v1",
            "retrievalProfileVersion": "tax-knowledge-search-v1",
            "embeddingModel": "BGE-M3",
            "rerankModel": "BAAI/bge-reranker-v2-m3",
            "policyCatalogSha256": "442761355510165265cb2eee3be8ee8a310c38ab7796a998ff1863073dbbd698",
            "evidenceRulesVersion": "knowledge-evidence-v1",
            "summaryPromptSha256": SUMMARY_PROMPT_V4_SHA256,
            "effectMetricVersion": "knowledge-effect-metrics-v2",
            "qualityPopulationMinimumRate": 0.9,
        },
        "indexSnapshotIds": [
            "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed",
            "99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2",
        ],
        "retrievalBinding": {
            "readAlias": "agent-doc-tax-policy-v2-read",
            "expectedIndexName": "agent-doc-tax-policy-v3-20260803-agent-read-v1",
            "expectedIndexUuid": "k97bn1gxROSfVm7zGfzbOg",
            "mappingVersion": "agent-knowledge-tax-v1",
            "policySnapshotId": "7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed",
            "lawSnapshotId": "99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2",
        },
        "assetHashes": [{"path": "agent-runtime/src/agent_runtime/bootstrap.py", "sha256": "a" * 64}],
        "preparedAt": "2026-08-28T12:00:00Z",
    }


def test_candidate_06_schema_binds_summary_v4_and_effect_metrics_v2() -> None:
    manifest = LiveP5Manifest.model_validate(_manifest_payload())

    assert manifest.schema_version == 4
    assert manifest.work_package_id == "WP-K-EFFECT-LIVE-06"
    assert manifest.task_versions == {"knowledge_rewrite": "1", "knowledge_summary": "4"}
    assert manifest.configuration_binding is not None
    assert manifest.configuration_binding.summary_prompt_sha256 == SUMMARY_PROMPT_V4_SHA256
    assert manifest.configuration_binding.effect_metric_version == "knowledge-effect-metrics-v2"
    assert manifest.configuration_binding.quality_population_minimum_rate == 0.9
    assert _candidate_id("candidate-06") == "candidate-06"


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("taskVersions", "knowledge_summary"), "3"),
        (("configurationBinding", "summaryPromptSha256"), "cf6318629fcc7e6156efa89e566e2083b84da94c2c783a041cf9f1338476ca22"),
        (("configurationBinding", "effectMetricVersion"), None),
        (("configurationBinding", "qualityPopulationMinimumRate"), None),
    ),
)
def test_candidate_06_rejects_version_or_metric_drift(path: tuple[str, str], value: object) -> None:
    payload = _manifest_payload()
    parent = payload[path[0]]
    assert isinstance(parent, dict)
    if value is None:
        parent.pop(path[1])
    else:
        parent[path[1]] = value

    with pytest.raises(ValidationError):
        LiveP5Manifest.model_validate(payload)


def test_candidate_06_authorization_template_remains_unconsumed() -> None:
    template = LiveAuthorizationTemplate.model_validate(
        {
            "schemaVersion": 1,
            "status": "awaiting_explicit_authorization",
            "workPackageId": "WP-K-EFFECT-LIVE-06",
            "runId": "knowledge-p5-live-v3-20260828-candidate-06",
            "authorizationReference": "P3_00:GATE-077",
            "singleUse": True,
            "maximumPaidRequests": 78,
            "retryAllowed": False,
            "answerRequestsAllowed": False,
            "liveP5Authorized": False,
            "datasetSha256": "1ea7417d80686545bd96d0f88f27b5b57de3de2ae6d6cb60c272190193645408",
            "requiredBindingFields": [
                "frozenHead",
                "runId",
                "manifestSha256",
                "authorizationReference",
                "maximumPaidRequests",
            ],
        }
    )

    assert template.live_p5_authorized is False
    assert template.maximum_paid_requests == 78


def test_candidate_06_authorization_record_requires_frozen_head_and_manifest_hash() -> None:
    payload = {
        "schemaVersion": 1,
        "status": "authorized_unconsumed",
        "workPackageId": "WP-K-EFFECT-LIVE-06",
        "runId": "knowledge-p5-live-v3-20260828-candidate-06",
        "authorizationReference": "P3_00:GATE-077",
        "singleUse": True,
        "maximumPaidRequests": 78,
        "retryAllowed": False,
        "answerRequestsAllowed": False,
        "liveP5Authorized": True,
        "datasetSha256": "1ea7417d80686545bd96d0f88f27b5b57de3de2ae6d6cb60c272190193645408",
        "principalProfileId": "tax-knowledge-admin-reader-v1",
        "readAuthorizationEvidenceRef": "WP-KRET-REAL-01:authorizationMatrix.admin",
        "jwtPersisted": False,
        "apiKeyPersisted": False,
        "confirmedBy": "project-maintainer",
        "confirmedAt": "2026-08-28T12:00:00Z",
    }

    with pytest.raises(ValidationError):
        LiveAuthorizationRecord.model_validate(payload)

    payload["frozenHead"] = "a" * 40
    payload["manifestSha256"] = "b" * 64
    authorization = LiveAuthorizationRecord.model_validate(payload)

    assert authorization.frozen_head == "a" * 40
    assert authorization.manifest_sha256 == "b" * 64


def test_candidate_06_allows_only_its_untracked_runtime_authorization_record() -> None:
    authorization_entry = (
        "?? agent-runtime/tests/evaluation/knowledge/live/evidence/"
        "knowledge-p5-live-v3-20260828-candidate-06.authorization.json"
    )

    assert _unexpected_live_worktree_entries(
        candidate_id="candidate-06", entries=(authorization_entry,)
    ) == ()
    assert _unexpected_live_worktree_entries(
        candidate_id="candidate-06",
        entries=(authorization_entry, " M agent-runtime/src/agent_runtime/bootstrap.py"),
    ) == (" M agent-runtime/src/agent_runtime/bootstrap.py",)
    assert _unexpected_live_worktree_entries(
        candidate_id="candidate-05", entries=(authorization_entry,)
    ) == (authorization_entry,)


def test_candidate_05_schema_and_hash_remain_unchanged() -> None:
    path = (
        REPOSITORY_ROOT
        / "agent-runtime/tests/evaluation/knowledge/live/evidence/"
        "knowledge-p5-live-v2-20260826-candidate-05.manifest.json"
    )
    manifest, digest = load_manifest(path)

    assert manifest.schema_version == 3
    assert manifest.task_versions == {"knowledge_rewrite": "1", "knowledge_summary": "3"}
    assert digest == "41997c6d41f3109b178844c9b74799bb59c869ae06ec23aca66bea1a6f1e278c"
