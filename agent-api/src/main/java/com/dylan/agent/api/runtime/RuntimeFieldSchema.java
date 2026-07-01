package com.dylan.agent.api.runtime;

import java.util.List;

import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AggregateFunction;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** 发送给 Runtime 的字段 schema，包含字段别名、允许的操作符、数据类型、格式提示和聚合函数白名单。 */
@Schema(description = "字段 schema，包含别名、允许操作符、数据类型和聚合函数白名单")
public class RuntimeFieldSchema {

    @Schema(description = "字段名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String name;

    @Schema(description = "字段别名", nullable = true)
    private List<String> aliases;

    @Schema(description = "允许的操作符列表", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<AgentOperator> operators;

    @Schema(description = "字段数据类型", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentFieldType type;

    @Schema(description = "格式提示（如 ISO-8601 datetime with timezone）", nullable = true)
    private String formatHint;

    @Schema(description = "支持的聚合函数列表。null 表示无 adapter（不应推断为完全允许），[] 表示仅允许 COUNT", nullable = true)
    private List<AggregateFunction> supportedAggregateFunctions;

    public RuntimeFieldSchema() {
    }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    public List<String> getAliases() { return aliases; }
    public void setAliases(List<String> aliases) { this.aliases = aliases; }
    public List<AgentOperator> getOperators() { return operators; }
    public void setOperators(List<AgentOperator> operators) { this.operators = operators; }
    public AgentFieldType getType() { return type; }
    public void setType(AgentFieldType type) { this.type = type; }
    public String getFormatHint() { return formatHint; }
    public void setFormatHint(String formatHint) { this.formatHint = formatHint; }
    public List<AggregateFunction> getSupportedAggregateFunctions() { return supportedAggregateFunctions; }
    public void setSupportedAggregateFunctions(List<AggregateFunction> supportedAggregateFunctions) { this.supportedAggregateFunctions = supportedAggregateFunctions; }
}
