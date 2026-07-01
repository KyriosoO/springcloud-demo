package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * Capability Routing Descriptor 的请求级安全投影。
 *
 * <p>这是 Capability Definition Descriptor 与 Available Capability 的投影交集，
 * 不是静态事实源。不包含 enabled/permissions/Handler 类名。
 */
@Schema(description = "Capability Routing Descriptor 请求投影")
public class RuntimeCapabilityRoutingDescriptor {

    @Schema(description = "capability 稳定标识", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(min = 1, max = 128)
    private String capabilityId;

    @Schema(description = "Plan 结构类型", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentPlanKind planKind;

    @Schema(description = "面向模型的能力描述", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(min = 1, max = 1000)
    private String description;

    @Schema(description = "适用条件，最多 20 项", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(max = 20)
    private List<String> applicability = Collections.emptyList();

    @Schema(description = "排除条件，最多 20 项", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    @Size(max = 20)
    private List<String> exclusions = Collections.emptyList();

    @Schema(description = "Domain Mode", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentDomainMode domainMode;

    @Schema(description = "当前请求允许的 domain 标识，去重。NONE 时为空，REQUIRED 时非空", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<String> allowedDomains = Collections.emptyList();

    public RuntimeCapabilityRoutingDescriptor() {
    }

    public String getCapabilityId() { return capabilityId; }
    public void setCapabilityId(String capabilityId) { this.capabilityId = capabilityId; }
    public AgentPlanKind getPlanKind() { return planKind; }
    public void setPlanKind(AgentPlanKind planKind) { this.planKind = planKind; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public List<String> getApplicability() { return applicability == null ? Collections.emptyList() : Collections.unmodifiableList(applicability); }
    public void setApplicability(List<String> applicability) { this.applicability = applicability == null ? null : new ArrayList<>(applicability); }
    public List<String> getExclusions() { return exclusions == null ? Collections.emptyList() : Collections.unmodifiableList(exclusions); }
    public void setExclusions(List<String> exclusions) { this.exclusions = exclusions == null ? null : new ArrayList<>(exclusions); }
    public AgentDomainMode getDomainMode() { return domainMode; }
    public void setDomainMode(AgentDomainMode domainMode) { this.domainMode = domainMode; }
    public List<String> getAllowedDomains() { return allowedDomains == null ? Collections.emptyList() : Collections.unmodifiableList(allowedDomains); }
    public void setAllowedDomains(List<String> allowedDomains) { this.allowedDomains = allowedDomains == null ? null : new ArrayList<>(allowedDomains); }
}
