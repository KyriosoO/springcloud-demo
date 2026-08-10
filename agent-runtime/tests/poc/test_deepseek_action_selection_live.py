from __future__ import annotations

import os
from pathlib import Path

import pytest

from agent_runtime.model.deepseek.transport import DeepSeekChatTransport, build_deepseek_http_client
from agent_runtime.model.settings import ModelSettings
from tests.poc.contracts import ActionPocRunAuthorization, validate_action_poc_manifest
from tests.poc.runner import run_action_poc


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DEEPSEEK_ACTION_V4_POC") != "1",
    reason="requires manifest-bound one-shot paid DeepSeek action v4 PoC opt-in",
)


@pytest.mark.asyncio
async def test_deepseek_action_selection_live() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    manifest_path = Path(os.environ["DEEPSEEK_ACTION_V4_MANIFEST_PATH"]).resolve()
    manifest, actual_manifest_sha256 = validate_action_poc_manifest(
        path=manifest_path,
        repository_root=repository_root,
    )
    authorization = ActionPocRunAuthorization(
        run_id=os.environ["DEEPSEEK_ACTION_V4_RUN_ID"],
        manifest_sha256=os.environ["DEEPSEEK_ACTION_V4_MANIFEST_SHA256"],
        authorization_reference=os.environ["DEEPSEEK_ACTION_V4_AUTHORIZATION_REF"],
    )
    if (
        actual_manifest_sha256 != authorization.manifest_sha256
        or manifest.run_id != authorization.run_id
    ):
        raise ValueError("poc.authorization_mismatch")

    env = dict(os.environ)
    env["AGENT_MODEL_PROVIDER"] = "deepseek"
    settings = ModelSettings.from_env(env)
    result_directory = Path(os.environ.get("DEEPSEEK_POC_RESULT_DIR", "tests/poc/results"))
    async with build_deepseek_http_client(settings) as client:
        result, path = await run_action_poc(
            transport=DeepSeekChatTransport(settings=settings, client=client),
            manifest_path=manifest_path,
            repository_root=repository_root,
            authorization=authorization,
            result_directory=result_directory,
            timeout_ms=settings.action_timeout_ms,
        )

    assert path.is_file()
    assert result.attempted_calls == 30
    assert result.conclusion == "passed"
    assert result.structure_valid_calls == 30
    assert result.expected_calls >= 27
    assert result.run_id == manifest.run_id
    assert result.manifest_sha256 == actual_manifest_sha256
