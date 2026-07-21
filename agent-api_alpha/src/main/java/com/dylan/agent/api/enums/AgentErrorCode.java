package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Agent 统一错误码枚举，按错误类别划分（权限、校验、Runtime、内部错误）。
 */
@Schema(description = "Agent 统一错误码")
public enum AgentErrorCode {
    @Schema(description = "无效请求")
    AGENT_INVALID_REQUEST,
    @Schema(description = "对话未找到")
    AGENT_CONVERSATION_NOT_FOUND,
    @Schema(description = "意图禁止访问")
    AGENT_INTENT_FORBIDDEN,
    @Schema(description = "字段禁止访问")
    AGENT_FIELD_FORBIDDEN,
    @Schema(description = "操作符禁止使用")
    AGENT_OPERATOR_FORBIDDEN,
    @Schema(description = "Plan 校验失败")
    AGENT_PLAN_INVALID,
    @Schema(description = "Runtime 不可用")
    AGENT_RUNTIME_UNAVAILABLE,
    @Schema(description = "查询失败")
    AGENT_QUERY_FAILED,
    @Schema(description = "内部错误")
    AGENT_INTERNAL_ERROR
}
