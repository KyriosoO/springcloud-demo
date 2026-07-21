package com.dylan.agent.api.contract.runtime.common;

import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AggregateFunction;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Plan 阶段的单体字段安全投影。
 */
@Schema(description = "Domain 字段投影")
public class RuntimeDomainFieldSchema {

    @Schema(description = "字段名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String field;

    @Schema(description = "字段别名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> aliases = Collections.emptyList();

    @Schema(description = "字段类型", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentFieldType type;

    @Schema(description = "允许的 operator", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotEmpty
    private List<AgentOperator> operators = Collections.emptyList();

    @Schema(description = "支持的聚合函数，空列表表示仅 COUNT", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<AggregateFunction> aggregateFunctions = Collections.emptyList();

    @Schema(description = "安全格式说明（仅格式，不含凭据或转义语义）", nullable = true)
    private String formatHint;

    public RuntimeDomainFieldSchema() {
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public List<String> getAliases() { return aliases == null ? Collections.emptyList() : Collections.unmodifiableList(aliases); }
    public void setAliases(List<String> aliases) { this.aliases = aliases == null ? null : new ArrayList<>(aliases); }
    public AgentFieldType getType() { return type; }
    public void setType(AgentFieldType type) { this.type = type; }
    public List<AgentOperator> getOperators() { return operators == null ? Collections.emptyList() : Collections.unmodifiableList(operators); }
    public void setOperators(List<AgentOperator> operators) { this.operators = operators == null ? null : new ArrayList<>(operators); }
    public List<AggregateFunction> getAggregateFunctions() { return aggregateFunctions == null ? Collections.emptyList() : Collections.unmodifiableList(aggregateFunctions); }
    public void setAggregateFunctions(List<AggregateFunction> aggregateFunctions) { this.aggregateFunctions = aggregateFunctions == null ? null : new ArrayList<>(aggregateFunctions); }
    public String getFormatHint() { return formatHint; }
    public void setFormatHint(String formatHint) { this.formatHint = formatHint; }
}
