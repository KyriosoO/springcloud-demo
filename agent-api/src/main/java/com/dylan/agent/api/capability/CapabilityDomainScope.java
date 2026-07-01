package com.dylan.agent.api.capability;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;

/** Capability 在单个 domain 上的可用范围。 */
@Schema(description = "Capability 在单个 domain 上的可用范围")
public class CapabilityDomainScope {

    @Schema(description = "业务域，例如 employee、transaction", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String domain;

    @Schema(description = "当前 capability 在该 domain 是否可用", requiredMode = Schema.RequiredMode.REQUIRED)
    private boolean enabled;

    @Schema(description = "不可用原因或状态原因，当前仅用于后续扩展", nullable = true)
    private String reasonCode;

    public CapabilityDomainScope() {
    }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
    public String getReasonCode() { return reasonCode; }
    public void setReasonCode(String reasonCode) { this.reasonCode = reasonCode; }
}
