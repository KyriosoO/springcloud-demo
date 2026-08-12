from __future__ import annotations

import os

import pytest

from agent_runtime.knowledge.evidence.summary_task_v2 import KnowledgeSummaryTaskV2
from tests.integration.knowledge import test_real_knowledge_egress_live as v1_harness
from tests.integration.knowledge.egress_v2_stability import (
    Gate043BudgetedSummaryTransport,
    write_v2_live_evidence,
)


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_KNOWLEDGE_EGRESS_V2_STABILITY") != "1",
    reason="requires explicit GATE-043 Knowledge egress V2 opt-in",
)


@pytest.mark.asyncio
async def test_gate043_real_retrieval_catalog_and_thirty_bounded_v2_summaries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The immutable V1 harness owns the already-audited retrieval, negative matrix,
    # budget denominator, and result aggregation. This isolated version binding
    # replaces only the task, transport authorization marker, and evidence writer.
    monkeypatch.setattr(v1_harness, "KnowledgeSummaryTaskV1", KnowledgeSummaryTaskV2)
    monkeypatch.setattr(v1_harness, "BudgetedSummaryTransport", Gate043BudgetedSummaryTransport)
    monkeypatch.setattr(v1_harness, "write_live_evidence", write_v2_live_evidence)

    await v1_harness.test_gate022_real_retrieval_catalog_and_thirty_bounded_summaries()
