package com.dylan.agent.api.response;

import com.dylan.agent.api.plan.AgentPlan;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/** Runtime plan 生成响应，包含 requestId 和候选 AgentPlan。 */
@Schema(description = "Runtime plan 生成响应")
public class PlanGenerateResponse {

    @Schema(description = "请求 ID", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String requestId;

    @Schema(description = "候选计划，无有效 plan 时为 null", nullable = true)
    private AgentPlan plan;

    public PlanGenerateResponse() {
    }

    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }
    public AgentPlan getPlan() { return plan; }
    public void setPlan(AgentPlan plan) { this.plan = plan; }
}
