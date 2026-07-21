package com.dylan.agent.api.plan;

import java.util.List;

import com.dylan.agent.api.enums.AgentOperator;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** Agent 查询过滤条件。multi-value 操作符使用 values 数组，单值/range 操作符使用 value。 */
@Schema(description = "查询过滤条件。多值操作符使用 values，单值/范围操作符使用 value")
public class AgentFilter {

    @Schema(description = "字段名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String field;

    @Schema(description = "操作符", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentOperator operator;

    @Schema(description = "单值/范围操作符的值", nullable = true)
    private String value;

    @Schema(description = "多值操作符的值列表", nullable = true)
    private List<String> values;

    public AgentFilter() {
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public AgentOperator getOperator() { return operator; }
    public void setOperator(AgentOperator operator) { this.operator = operator; }
    public String getValue() { return value; }
    public void setValue(String value) { this.value = value; }
    public List<String> getValues() { return values; }
    public void setValues(List<String> values) { this.values = values; }
}
