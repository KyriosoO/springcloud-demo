package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/** QUERY 明细结果排序规格。 */
@Schema(description = "QUERY 明细结果排序规格")
public class AgentSortSpec {

    @Schema(description = "canonical 字段名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String field;

    @Schema(description = "排序方向：ASC 或 DESC", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = {"ASC", "DESC"})
    @NotBlank
    private String direction;

    public AgentSortSpec() {
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
}
