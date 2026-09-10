"""Non-live boundary probes, not reconstruction of an unknown real model response."""
import asyncio
import json

import httpx
import pytest

from agent_runtime.knowledge.rewrite_v3 import KnowledgeSemanticPlanInput
from agent_runtime.knowledge.rewrite_v9 import KnowledgeRewriteTaskV9
from agent_runtime.model.contracts import ModelCallContext, ModelProviderFailureKind
from agent_runtime.model.deepseek.transport import DeepSeekChatTransport
from agent_runtime.model.gateway import BoundedStructuredModelGateway
from agent_runtime.model.settings import ModelApiKey, ModelProvider, ModelSettings


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", [None, "envelope", "truncated", "json", "extra_field", "missing_requirements", "content_type"])
async def test_distinct_response_errors_share_invalid_output_without_retry(fault):
    question = "车辆购置税法规定，购买自用应税车辆的计税价格是否包括增值税？"
    # A declared valid lookup demonstrates expressibility only; it is not LLM output.
    plan = {
        "outcome": "search", "question_kind": "lookup",
        "queries": [{"domain_id": "tax.law", "query": question}],
        "requirements": [{"requirement_id": "r1", "domain_id": "tax.law", "kind": "rule", "focus": question}],
        "missing_conditions": [],
    }
    if fault == "extra_field":
        plan["extra"] = True
    if fault == "missing_requirements":
        del plan["requirements"]
    content = "{" if fault == "json" else json.dumps(plan, ensure_ascii=False)
    body = {
        "object": "invalid" if fault == "envelope" else "chat.completion",
        "model": ModelSettings.MODEL_NAME,
        "choices": [{"index": 0, "finish_reason": "length" if fault == "truncated" else "stop",
                     "message": {"role": "assistant", "content": content}}],
    }
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, content=json.dumps(body).encode(),
                              headers={"content-type": "text/plain" if fault == "content_type" else "application/json"})

    settings = ModelSettings(provider=ModelProvider.DEEPSEEK, api_key=ModelApiKey("synthetic-nonlive-only"))
    async with httpx.AsyncClient(base_url=settings.BASE_URL, transport=httpx.MockTransport(handler), trust_env=False) as client:
        definition = KnowledgeRewriteTaskV9.definition()
        gateway = BoundedStructuredModelGateway(
            transport=DeepSeekChatTransport(settings=settings, client=client),
            definitions=(definition,), max_concurrency=1,
        )
        result = await gateway.generate(
            definition=definition,
            input=KnowledgeSemanticPlanInput(minimized_question=question, enabled_domain_ids=("tax.law",)),
            context=ModelCallContext(request_id="nonlive-lookup", correlation_id="nonlive-boundary",
                                     deadline_monotonic=asyncio.get_running_loop().time() + 10),
        )
        assert calls == ["/chat/completions"]
        if fault is None:
            assert result.failure_kind is None and result.output is not None
            assert result.output.outcome == "search"
            assert [(q.domain_id, q.query) for q in result.output.queries] == [("tax.law", question)]
        else:
            assert result.failure_kind is ModelProviderFailureKind.INVALID_OUTPUT
            assert result.output is None
    assert client.is_closed
