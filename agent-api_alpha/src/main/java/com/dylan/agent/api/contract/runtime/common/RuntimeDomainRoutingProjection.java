package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Route 阶段的最小 domain 投影：仅标识、别名和描述，不含 field schema。
 */
@Schema(description = "Route 阶段 domain 投影")
public class RuntimeDomainRoutingProjection {

    @Schema(description = "domain 标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String domain;

    @Schema(description = "domain 别名", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> aliases = Collections.emptyList();

    @Schema(description = "domain 描述", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String description;

    public RuntimeDomainRoutingProjection() {
    }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public List<String> getAliases() { return aliases == null ? Collections.emptyList() : Collections.unmodifiableList(aliases); }
    public void setAliases(List<String> aliases) { this.aliases = aliases == null ? null : new ArrayList<>(aliases); }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
}
