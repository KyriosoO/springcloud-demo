"""文档改写 Runtime planner 测试。"""

from __future__ import annotations

import pytest

from app.core.document_rewrite import DocumentRewriteRequest, RuntimeDocumentRewritePlanner


class FakeLlmClient:
    model_name = "fake-model"

    def __init__(self, raw: str):
        self.raw = raw

    async def generate_plan_json(self, system_prompt, user_payload):
        self.system_prompt = system_prompt
        self.user_payload = user_payload
        return self.raw


def _request(max_candidates: int = 2) -> DocumentRewriteRequest:
    return DocumentRewriteRequest(
        requestId="inv-1",
        query="查询增值税优惠",
        domain="policy_document",
        materialType="tax_policy",
        language="zh-CN",
        maxCandidates=max_candidates,
        timeoutMs=1000,
    )


@pytest.mark.asyncio
async def test_rewrite_normalizes_candidates_and_caps_count():
    client = FakeLlmClient("""
        {
          "candidates": [
            {"text": " 小规模纳税人 增值税优惠 ", "intentLabel": " tax ", "confidence": 0.9},
            {"text": "小规模纳税人 增值税优惠", "confidence": 0.8},
            {"text": "企业所得税优惠", "confidence": 1.2}
          ]
        }
    """)
    planner = RuntimeDocumentRewritePlanner(client)

    response = await planner.rewrite(_request(max_candidates=2))

    assert [candidate.text for candidate in response.candidates] == [
        "小规模纳税人 增值税优惠",
        "企业所得税优惠",
    ]
    assert response.candidates[0].intent_label == "tax"
    assert response.candidates[1].confidence == 1.0
    assert response.model == "fake-model"
    assert response.diagnostic_id.startswith("runtime-rewrite-")
    assert "requestData" in client.user_payload


@pytest.mark.asyncio
async def test_rewrite_drops_candidates_when_llm_returns_forbidden_execution_fields():
    client = FakeLlmClient("""
        {
          "candidates": [
            {"text": "小规模纳税人增值税优惠", "filter": {"tenantId": "t1"}}
          ]
        }
    """)
    planner = RuntimeDocumentRewritePlanner(client)

    response = await planner.rewrite(_request())

    assert response.candidates == []
