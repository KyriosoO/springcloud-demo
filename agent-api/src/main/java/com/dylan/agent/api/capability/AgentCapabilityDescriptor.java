package com.dylan.agent.api.capability;

import java.util.List;

import com.dylan.agent.api.enums.AgentIntent;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** 单个 Agent capability 的标准化 descriptor，由 Java 生成并下发给 Runtime。 */
@Schema(description = "Agent capability descriptor")
public class AgentCapabilityDescriptor {

    @Schema(description = "稳定能力 ID，例如 query.search", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String capabilityId;

    @Schema(description = "当前 plan intent", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentIntent intent;

    @Schema(description = "给 Runtime/prompt 使用的短名称", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String displayName;

    @Schema(description = "能力说明", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String description;

    @Schema(description = "支持的 domain scope。不绑定 domain 的能力使用空列表，例如 clarify.ask", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private List<@Valid CapabilityDomainScope> domainScopes;

    @Schema(description = "风险等级", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentCapabilityRiskLevel riskLevel;

    @Schema(description = "执行模式", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private AgentCapabilityExecutionMode executionMode;

    @Schema(description = "输入契约引用", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private CapabilityContractRef inputContract;

    @Schema(description = "输出契约引用", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private CapabilityContractRef outputContract;

    @Schema(description = "上下文读写声明", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private CapabilityContextSpec context;

    @Schema(description = "权限说明，不下发具体角色", nullable = true)
    private List<String> permissions;

    @Schema(description = "是否当前可用", requiredMode = Schema.RequiredMode.REQUIRED)
    private boolean enabled;

    public AgentCapabilityDescriptor() {
    }

    public String getCapabilityId() { return capabilityId; }
    public void setCapabilityId(String capabilityId) { this.capabilityId = capabilityId; }
    public AgentIntent getIntent() { return intent; }
    public void setIntent(AgentIntent intent) { this.intent = intent; }
    public String getDisplayName() { return displayName; }
    public void setDisplayName(String displayName) { this.displayName = displayName; }
    public String getDescription() { return description; }
    public void setDescription(String description) { this.description = description; }
    public List<CapabilityDomainScope> getDomainScopes() { return domainScopes; }
    public void setDomainScopes(List<CapabilityDomainScope> domainScopes) { this.domainScopes = domainScopes; }
    public AgentCapabilityRiskLevel getRiskLevel() { return riskLevel; }
    public void setRiskLevel(AgentCapabilityRiskLevel riskLevel) { this.riskLevel = riskLevel; }
    public AgentCapabilityExecutionMode getExecutionMode() { return executionMode; }
    public void setExecutionMode(AgentCapabilityExecutionMode executionMode) { this.executionMode = executionMode; }
    public CapabilityContractRef getInputContract() { return inputContract; }
    public void setInputContract(CapabilityContractRef inputContract) { this.inputContract = inputContract; }
    public CapabilityContractRef getOutputContract() { return outputContract; }
    public void setOutputContract(CapabilityContractRef outputContract) { this.outputContract = outputContract; }
    public CapabilityContextSpec getContext() { return context; }
    public void setContext(CapabilityContextSpec context) { this.context = context; }
    public List<String> getPermissions() { return permissions; }
    public void setPermissions(List<String> permissions) { this.permissions = permissions; }
    public boolean isEnabled() { return enabled; }
    public void setEnabled(boolean enabled) { this.enabled = enabled; }
}
