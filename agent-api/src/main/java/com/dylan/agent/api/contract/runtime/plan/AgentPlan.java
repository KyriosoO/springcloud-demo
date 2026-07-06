package com.dylan.agent.api.contract.runtime.plan;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import io.swagger.v3.oas.annotations.media.DiscriminatorMapping;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * AgentPlan sealed union。Query、Aggregate 和 Document 是当前合法子类型。
 *
 * <p>不包含澄清变体、独立版本轴、capability 身份或 domain 身份字段。
 * 澄清只能通过 ClarificationRequired outcome 表达。
 */
@Schema(
    description = "Agent Plan 联合类型",
    oneOf = {QueryAgentPlan.class, AggregateAgentPlan.class, DocumentAgentPlan.class},
    discriminatorProperty = "planKind",
    discriminatorMapping = {
        @DiscriminatorMapping(value = "QUERY", schema = QueryAgentPlan.class),
        @DiscriminatorMapping(value = "AGGREGATE", schema = AggregateAgentPlan.class),
        @DiscriminatorMapping(value = "DOCUMENT", schema = DocumentAgentPlan.class)
    }
)
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.EXISTING_PROPERTY, property = "planKind", visible = true)
@JsonSubTypes({
    @JsonSubTypes.Type(value = QueryAgentPlan.class, name = "QUERY"),
    @JsonSubTypes.Type(value = AggregateAgentPlan.class, name = "AGGREGATE"),
    @JsonSubTypes.Type(value = DocumentAgentPlan.class, name = "DOCUMENT")
})
public sealed interface AgentPlan
    permits QueryAgentPlan, AggregateAgentPlan, DocumentAgentPlan {

    /** Plan 结构类型 discriminator。 */
    AgentPlanKind getPlanKind();
}
