package com.dylan.agent.api.contract.runtime.plan;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOutcomeType;
import io.swagger.v3.oas.annotations.media.DiscriminatorMapping;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Plan 阶段的封闭 outcome union：Executable 或 Clarification。
 *
 * <p>不包含 DECISION —— DECISION 只属于 RouteOutcome。
 * 封闭性由显式 Jackson/OpenAPI mapping 与架构测试保证；未命名 Java 模块
 * 无法跨包声明 ClarificationRequired 为 permitted subtype。
 */
@Schema(
    description = "Plan Outcome 联合类型",
    oneOf = {ExecutablePlan.class, ClarificationRequired.class},
    discriminatorProperty = "outcomeType",
    discriminatorMapping = {
        @DiscriminatorMapping(value = "EXECUTABLE", schema = ExecutablePlan.class),
        @DiscriminatorMapping(value = "CLARIFICATION", schema = ClarificationRequired.class)
    }
)
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.EXISTING_PROPERTY, property = "outcomeType", visible = true)
@JsonSubTypes({
    @JsonSubTypes.Type(value = ExecutablePlan.class, name = "EXECUTABLE"),
    @JsonSubTypes.Type(value = ClarificationRequired.class, name = "CLARIFICATION")
})
public interface PlanOutcome {

    RuntimeOutcomeType getOutcomeType();
    String getRequestId();
    RuntimeOperationMetadata getMetadata();
}
