package com.dylan.agent.api.contract.runtime.plan;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

/**
 * AGGREGATE 结构化计划。
 */
@Schema(description = "AGGREGATE Plan 子类型")
@JsonTypeName("AGGREGATE")
public final class AggregateAgentPlan implements AgentPlan {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "AGGREGATE")
    @NotNull
    private final AgentPlanKind planKind = AgentPlanKind.AGGREGATE;

    @Schema(description = "聚合规格", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private AgentAggregateSpec aggregate;

    public AggregateAgentPlan() {
    }

    @Override
    public AgentPlanKind getPlanKind() { return planKind; }

    public AgentAggregateSpec getAggregate() { return aggregate; }
    public void setAggregate(AgentAggregateSpec aggregate) { this.aggregate = aggregate; }
}
