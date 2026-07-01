package com.dylan.agent.api.plan;

import com.dylan.agent.api.enums.AgentIntent;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** Runtime 输出的候选结构化计划，Java 侧仍需重新校验。QUERY 时 query 必填 clarify/aggregate 为空；CLARIFY 时 clarify 必填 query/aggregate 为空；AGGREGATE 时 aggregate 必填 query/clarify 为空。 */
@Schema(description = "Runtime 输出的候选结构化计划")
public class AgentPlan {

    @Schema(description = "契约版本号", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "1.0")
    @NotBlank
    private String planVersion;

    @Schema(description = "顶层意图", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentIntent intent;

    @Schema(description = "目标业务域", nullable = true)
    private String domain;

    @Schema(description = "QUERY 计划时必填，其他 intent 时必须为 null", nullable = true)
    private AgentQuerySpec query;

    @Schema(description = "CLARIFY 计划时必填，其他 intent 时必须为 null", nullable = true)
    private ClarifySpec clarify;

    @Schema(description = "AGGREGATE 计划时必填，其他 intent 时必须为 null", nullable = true)
    private AgentAggregateSpec aggregate;

    public AgentPlan() {
    }

    public String getPlanVersion() { return planVersion; }
    public void setPlanVersion(String planVersion) { this.planVersion = planVersion; }
    public AgentIntent getIntent() { return intent; }
    public void setIntent(AgentIntent intent) { this.intent = intent; }
    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public AgentQuerySpec getQuery() { return query; }
    public void setQuery(AgentQuerySpec query) { this.query = query; }
    public ClarifySpec getClarify() { return clarify; }
    public void setClarify(ClarifySpec clarify) { this.clarify = clarify; }
    public AgentAggregateSpec getAggregate() { return aggregate; }
    public void setAggregate(AgentAggregateSpec aggregate) { this.aggregate = aggregate; }
}
