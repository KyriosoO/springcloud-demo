package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;
import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Agent 成功结果 payload 的唯一扩展点。
 *
 * <p>新增结果形状必须扩展该 sealed 层级，不能在 {@link AgentChatResponse}
 * 上增加并列字段。
 */
public sealed interface AgentResultPayload
        permits QueryAgentResultPayload, QueryPreviewResultPayload, AggregateAgentResultPayload, DocumentAgentResultPayload {

    @JsonProperty(value = "resultKind", access = JsonProperty.Access.READ_ONLY)
    AgentResultKind getResultKind();
}
