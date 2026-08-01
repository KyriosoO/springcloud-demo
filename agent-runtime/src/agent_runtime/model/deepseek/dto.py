from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from agent_runtime.capability_api.contracts import JsonObject, JsonValue, freeze_json_object
from agent_runtime.model.contracts import (
    InvalidModelOutput,
    StructuredFinishKind,
    StructuredModelRequest,
    StructuredModelResponse,
    StructuredOutputMode,
    StructuredToolCall,
    StructuredToolMode,
)
from agent_runtime.model.deepseek.json_codec import parse_unique_json_object
from agent_runtime.model.settings import ModelSettings


@dataclass(frozen=True, slots=True, kw_only=True)
class DeepSeekRequest:
    payload: JsonObject

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "payload",
            freeze_json_object(
                self.payload,
                max_bytes=262144,
                max_depth=20,
                max_collection_items=4096,
            ),
        )


def project_deepseek_request(request: StructuredModelRequest) -> DeepSeekRequest:
    messages: tuple[JsonValue, ...] = (
        {"role": "system", "content": request.system_instruction},
        {"role": "user", "content": request.user_payload_json},
    )
    payload: dict[str, JsonValue] = {
        "model": ModelSettings.MODEL_NAME,
        "messages": messages,
        "thinking": {"type": "disabled"},
        "stream": False,
        "temperature": 0,
        "max_tokens": request.max_output_tokens,
    }
    if request.tool_mode is StructuredToolMode.REQUIRED:
        payload["tools"] = tuple(
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.arguments_schema,
                },
            }
            for tool in request.tools
        )
        payload["tool_choice"] = "required"
    elif request.output_mode is StructuredOutputMode.JSON_OBJECT:
        payload["response_format"] = {"type": "json_object"}
    else:
        raise InvalidModelOutput("model.invalid_request_projection")
    return DeepSeekRequest(payload=payload)


def _required_mapping(value: object, code: str) -> Mapping[str, JsonValue]:
    if not isinstance(value, Mapping):
        raise InvalidModelOutput(code)
    return cast(Mapping[str, JsonValue], value)


def parse_deepseek_response(raw: bytes, *, max_bytes: int) -> StructuredModelResponse:
    value = parse_unique_json_object(raw, max_bytes=max_bytes, max_depth=20, max_items=4096)
    if value.get("object") != "chat.completion" or value.get("model") != ModelSettings.MODEL_NAME:
        raise InvalidModelOutput("model.provider_response_mismatch")
    choices = value.get("choices")
    if not isinstance(choices, tuple) or len(choices) != 1:
        raise InvalidModelOutput("model.provider_choices_invalid")
    choice = _required_mapping(choices[0], "model.provider_choice_invalid")
    if choice.get("index") != 0 or isinstance(choice.get("index"), bool):
        raise InvalidModelOutput("model.provider_choice_invalid")
    finish_reason = choice.get("finish_reason")
    if finish_reason not in (StructuredFinishKind.TOOL_CALLS.value, StructuredFinishKind.STOP.value):
        raise InvalidModelOutput("model.provider_finish_reason_invalid")
    message = _required_mapping(choice.get("message"), "model.provider_message_invalid")
    content = message.get("content")
    if content is not None and not isinstance(content, str):
        raise InvalidModelOutput("model.provider_content_invalid")
    tool_calls_value = message.get("tool_calls", ())
    if not isinstance(tool_calls_value, tuple):
        raise InvalidModelOutput("model.provider_tool_calls_invalid")
    tool_calls: list[StructuredToolCall] = []
    for raw_call in tool_calls_value:
        call = _required_mapping(raw_call, "model.provider_tool_call_invalid")
        if call.get("type") != "function":
            raise InvalidModelOutput("model.provider_tool_call_invalid")
        function = _required_mapping(call.get("function"), "model.provider_tool_call_invalid")
        name = function.get("name")
        arguments = function.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, str):
            raise InvalidModelOutput("model.provider_tool_call_invalid")
        tool_calls.append(StructuredToolCall(name=name, arguments_json=arguments))
    usage_total_tokens = None
    usage = value.get("usage")
    if usage is not None:
        usage_mapping = _required_mapping(usage, "model.provider_usage_invalid")
        total_tokens = usage_mapping.get("total_tokens")
        if not isinstance(total_tokens, int) or isinstance(total_tokens, bool) or total_tokens < 0:
            raise InvalidModelOutput("model.provider_usage_invalid")
        usage_total_tokens = total_tokens
    return StructuredModelResponse(
        finish_kind=StructuredFinishKind(cast(str, finish_reason)),
        content=content,
        tool_calls=tuple(tool_calls),
        usage_total_tokens=usage_total_tokens,
    )
