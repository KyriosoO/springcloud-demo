package com.dylan.agent.api.contract.runtime.clarification;

import com.fasterxml.jackson.annotation.JsonTypeName;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** domain 候选列表 args。合法绑定 reasonCode: DOMAIN_REQUIRED, DOMAIN_AMBIGUOUS。 */
@Schema(description = "domain 候选列表")
@JsonTypeName("DOMAIN_CHOICES")
public final class DomainChoiceArgs implements ClarificationArgs {

    @Schema(description = "固定 discriminator", requiredMode = Schema.RequiredMode.REQUIRED, allowableValues = "DOMAIN_CHOICES")
    @NotNull
    private final ClarificationArgType argType = ClarificationArgType.DOMAIN_CHOICES;

    @Schema(description = "候选 domain 列表（1～20，去重）", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(min = 1, max = 20)
    private List<String> domains = Collections.emptyList();

    public DomainChoiceArgs() {
    }

    @Override
    public ClarificationArgType getArgType() { return argType; }

    public List<String> getDomains() {
        return domains == null ? Collections.emptyList() : Collections.unmodifiableList(domains);
    }
    public void setDomains(List<String> domains) {
        this.domains = domains == null ? null : new ArrayList<>(domains);
    }
}
