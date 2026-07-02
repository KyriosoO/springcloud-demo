"""兼容 OpenAI 的大模型客户端。"""

import json
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI

from app.core.errors import RuntimeProviderError, RuntimeTimeoutError
from app.core.settings import Settings, get_settings


class LlmClient:
    """使用固定配置包装大模型客户端。"""

    def __init__(self, settings: Settings):
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            max_retries=0,
        )
        self._model = settings.llm_model
        self._timeout = settings.llm_timeout_seconds

    async def generate_plan_json(
        self,
        system_prompt: str,
        user_payload: dict[str, Any],
    ) -> str:
        """发送计划生成请求，返回大模型原始 JSON 文本。"""
        return await self._call_llm(system_prompt, user_payload)

    async def repair_json(
        self,
        repair_system_prompt: str,
        invalid_output: str,
        validation_errors: list[str],
        user_payload: dict[str, Any],
    ) -> str:
        """发送通用 JSON 修复请求，不假设特定意图或计划结构。"""
        repair_payload = {
            "invalidOutput": invalid_output,
            "validationErrors": validation_errors,
            "requestData": user_payload,
        }
        return await self._call_llm(repair_system_prompt, repair_payload)

    async def _call_llm(self, system_prompt: str, user_payload: dict[str, Any]) -> str:
        """发送系统消息和用户消息到大模型，返回原始文本响应。

        超时异常映射为运行时超时，其他提供方错误映射为运行时提供方异常。
        """
        user_content = json.dumps(user_payload, ensure_ascii=False)

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                temperature=0.0,
                max_tokens=1200,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                timeout=self._timeout,
            )
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise RuntimeTimeoutError(f"LLM call timed out after {self._timeout}s")
            raise RuntimeProviderError(f"LLM provider error: {type(e).__name__}")

        content = response.choices[0].message.content
        if not content:
            raise RuntimeProviderError("LLM returned empty response")

        return content.strip()


@lru_cache
def get_llm_client() -> LlmClient:
    """缓存的大模型客户端单例工厂函数。"""
    return LlmClient(get_settings())
