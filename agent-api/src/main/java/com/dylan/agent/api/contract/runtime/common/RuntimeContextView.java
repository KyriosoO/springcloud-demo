package com.dylan.agent.api.contract.runtime.common;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;
import io.swagger.v3.oas.annotations.media.DiscriminatorMapping;
import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Plan 阶段的 Context 只读最小投影 —— sealed union。
 *
 * <p>PlanRequest 只接收安全 Context View，不接收完整持久化 Envelope 或 Owner/Write 权限。
 */
@Schema(
    description = "Runtime Context View 联合类型",
    oneOf = {RuntimeQueryContextView.class, RuntimeAggregateContextView.class},
    discriminatorProperty = "contextType",
    discriminatorMapping = {
        @DiscriminatorMapping(value = "QUERY", schema = RuntimeQueryContextView.class),
        @DiscriminatorMapping(value = "AGGREGATE", schema = RuntimeAggregateContextView.class)
    }
)
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.EXISTING_PROPERTY, property = "contextType", visible = true)
@JsonSubTypes({
    @JsonSubTypes.Type(value = RuntimeQueryContextView.class, name = "QUERY"),
    @JsonSubTypes.Type(value = RuntimeAggregateContextView.class, name = "AGGREGATE")
})
public sealed interface RuntimeContextView
    permits RuntimeQueryContextView, RuntimeAggregateContextView {

    /** Context discriminator。 */
    RuntimeContextType getContextType();

    /** 来源 Invocation 标识。 */
    String getSourceInvocationId();
}
