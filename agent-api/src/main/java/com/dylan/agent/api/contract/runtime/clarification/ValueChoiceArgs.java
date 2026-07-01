package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** 值候选列表 args。合法绑定 reasonCode: VALUE_REQUIRED, VALUE_AMBIGUOUS。 */
@Schema(description = "值候选列表")
@JsonTypeName("VALUE_CHOICES")
public final class ValueChoiceArgs implements ClarificationArgs {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "VALUE_CHOICES")
    @NotNull
    private final ClarificationArgType argType = ClarificationArgType.VALUE_CHOICES;

    @Schema(description = "目标字段名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String field;

    @Schema(description = "候选值列表（0～50，VALUE_REQUIRED 允许空列表）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(max = 50)
    private List<String> values = Collections.emptyList();

    public ValueChoiceArgs() {
    }

    @Override
    public ClarificationArgType getArgType() { return argType; }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public List<String> getValues() {
        return values == null ? Collections.emptyList() : Collections.unmodifiableList(values);
    }
    public void setValues(List<String> values) {
        this.values = values == null ? null : new ArrayList<>(values);
    }
}
