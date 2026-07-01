package com.dylan.agent.api.contract.runtime.plan;

import com.fasterxml.jackson.annotation.JsonTypeName;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.plan.AgentQuerySpec;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;

/**
 * QUERY 结构化计划。
 */
@Schema(description = "QUERY Plan 子类型")
@JsonTypeName("QUERY")
public final class QueryAgentPlan implements AgentPlan {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "QUERY")
    @NotNull
    private final AgentPlanKind planKind = AgentPlanKind.QUERY;

    @Schema(description = "查询规格", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Valid
    private AgentQuerySpec query;

    public QueryAgentPlan() {
    }

    @Override
    public AgentPlanKind getPlanKind() { return planKind; }

    public AgentQuerySpec getQuery() { return query; }
    public void setQuery(AgentQuerySpec query) { this.query = query; }
}
