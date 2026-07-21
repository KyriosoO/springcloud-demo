package com.dylan.agent.api.capability;

import io.swagger.v3.oas.annotations.media.Schema;

/** API 级 capability 风险等级。当前仅有 READ_ONLY；确认链路实施后扩展 CONFIRM_REQUIRED、HIGH_RISK_CONFIRM_REQUIRED。 */
@Schema(description = "Capability 风险等级")
public enum AgentCapabilityRiskLevel {
    @Schema(description = "无副作用，可直接执行")
    READ_ONLY
}
