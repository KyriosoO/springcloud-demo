package com.dylan.agent.api.capability;

import io.swagger.v3.oas.annotations.media.Schema;

/** API 级 capability 执行模式。当前仅有 IMMEDIATE；pending-confirmation 链路实施后扩展。 */
@Schema(description = "Capability 执行模式")
public enum AgentCapabilityExecutionMode {
    @Schema(description = "立即执行，无需确认")
    IMMEDIATE
}
