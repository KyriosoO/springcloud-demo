package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** 字段候选列表 args。合法绑定 reasonCode: FIELD_REQUIRED。 */
@Schema(description = "字段候选列表")
@JsonTypeName("FIELD_CHOICES")
public final class FieldChoiceArgs implements ClarificationArgs {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "FIELD_CHOICES")
    @NotNull
    private final ClarificationArgType argType = ClarificationArgType.FIELD_CHOICES;

    @Schema(description = "候选字段列表（1～50，去重）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(min = 1, max = 50)
    private List<String> fields = Collections.emptyList();

    public FieldChoiceArgs() {
    }

    @Override
    public ClarificationArgType getArgType() { return argType; }

    public List<String> getFields() {
        return fields == null ? Collections.emptyList() : Collections.unmodifiableList(fields);
    }
    public void setFields(List<String> fields) {
        this.fields = fields == null ? null : new ArrayList<>(fields);
    }
}
