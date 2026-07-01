package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** capability 候选列表 args。合法绑定 reasonCode: CAPABILITY_AMBIGUOUS。 */
@Schema(description = "capability 候选列表")
@JsonTypeName("CAPABILITY_CHOICES")
public final class CapabilityChoiceArgs implements ClarificationArgs {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "CAPABILITY_CHOICES")
    @NotNull
    private final ClarificationArgType argType = ClarificationArgType.CAPABILITY_CHOICES;

    @Schema(description = "候选 capabilityId 列表（2～20，去重）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(min = 2, max = 20)
    private List<String> capabilityIds = Collections.emptyList();

    public CapabilityChoiceArgs() {
    }

    @Override
    public ClarificationArgType getArgType() { return argType; }

    public List<String> getCapabilityIds() {
        return capabilityIds == null ? Collections.emptyList() : Collections.unmodifiableList(capabilityIds);
    }
    public void setCapabilityIds(List<String> capabilityIds) {
        this.capabilityIds = capabilityIds == null ? null : new ArrayList<>(capabilityIds);
    }
}
