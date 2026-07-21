package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

/** 聚合结果排序规格：排序字段 + 方向（ASC/DESC）。排序字段必须来自 groupByFields 或 metric alias。 */
@Schema(description = "聚合结果排序规格")
public class AggregateOrderSpec {

    @Schema(description = "排序字段名，来自 groupByFields 或 metric alias", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String field;

    @Schema(description = "排序方向", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = {"ASC", "DESC"})
    @NotBlank
    @Pattern(regexp = "^(ASC|DESC)$")
    private String direction;

    public AggregateOrderSpec() {
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
}
