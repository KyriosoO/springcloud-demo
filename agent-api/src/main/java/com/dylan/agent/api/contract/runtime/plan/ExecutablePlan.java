package com.dylan.agent.api.contract.runtime.plan;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOutcomeType;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/**
 * Plan 阶段的可执行 outcome。
 *
 * <p>只聚合 plan + metadata，不携带顶层 capabilityId、planKind、domain、
 * Validated Plan、最终授权或业务结果。这些字段由 D02/D03 在 PlanningResult 中附着。
 */
@Schema(description = "可执行 plan outcome")
@JsonTypeName("EXECUTABLE")
public final class ExecutablePlan implements PlanOutcome {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "EXECUTABLE")
    @NotNull
    private final RuntimeOutcomeType outcomeType = RuntimeOutcomeType.EXECUTABLE;

    @Schema(description = "请求关联标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String requestId;

    @Schema(description = "候选计划", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private AgentPlan plan;

    @Schema(description = "操作元数据", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private RuntimeOperationMetadata metadata;

    public ExecutablePlan() {
    }

    @Override
    public RuntimeOutcomeType getOutcomeType() { return outcomeType; }

    @Override
    public String getRequestId() { return requestId; }
    public void setRequestId(String requestId) { this.requestId = requestId; }

    public AgentPlan getPlan() { return plan; }
    public void setPlan(AgentPlan plan) { this.plan = plan; }

    @Override
    public RuntimeOperationMetadata getMetadata() { return metadata; }
    public void setMetadata(RuntimeOperationMetadata metadata) { this.metadata = metadata; }
}
