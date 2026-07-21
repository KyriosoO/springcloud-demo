package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** 字段禁止访问 args。合法绑定 reasonCode: FIELD_FORBIDDEN。 */
@Schema(description = "字段禁止访问")
@JsonTypeName("FIELD_FORBIDDEN")
public final class FieldForbiddenArgs implements ClarificationArgs {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED,
            allowableValues = "FIELD_FORBIDDEN")
    @NotNull
    private final ClarificationArgType argType = ClarificationArgType.FIELD_FORBIDDEN;

    @Schema(description = "用户请求但当前不可访问的字段或字段描述", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String field;

    public FieldForbiddenArgs() {
    }

    @Override
    public ClarificationArgType getArgType() { return argType; }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
}
