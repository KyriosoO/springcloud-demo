from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.settings import ModelSettings
from tests.poc.runner import run_answer_poc


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DEEPSEEK_POC") != "1",
    reason="requires explicit paid DeepSeek PoC opt-in",
)


@pytest.mark.asyncio
async def test_deepseek_answer_generation_live() -> None:
    env = dict(os.environ)
    env["AGENT_MODEL_PROVIDER"] = "deepseek"
    settings = ModelSettings.from_env(env)
    result_directory = Path(os.environ.get("DEEPSEEK_POC_RESULT_DIR", "tests/poc/results"))
    async with build_deepseek_http_client(settings) as client:
        result, path = await run_answer_poc(
            transport=DeepSeekChatTransport(settings=settings, client=client),
            result_directory=result_directory,
            timeout_ms=settings.answer_timeout_ms,
        )

    assert path.is_file()
    assert result.attempted_calls == 6
    assert result.conclusion == "passed"
    assert result.structure_valid_calls == 6
    assert result.grounding_expected_calls == 6
