package com.dylan.agent.api.plan;

import com.dylan.agent.api.enums.AggregateFunction;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/** 聚合指标规格：别名 + 聚合函数 + 目标字段（COUNT 时字段可为空）。 */
@Schema(description = "聚合指标规格")
public class AggregateMetricSpec {

    @Schema(description = "指标别名，结果集中使用，必须唯一", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(max = 50)
    private String alias;

    @Schema(description = "聚合函数", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AggregateFunction function;

    @Schema(description = "目标字段名，COUNT 时为 null", nullable = true)
    private String field;

    public AggregateMetricSpec() {
    }

    public String getAlias() { return alias; }
    public void setAlias(String alias) { this.alias = alias; }
    public AggregateFunction getFunction() { return function; }
    public void setFunction(AggregateFunction function) { this.function = function; }
    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
}
