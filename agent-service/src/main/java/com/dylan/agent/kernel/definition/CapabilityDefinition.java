package com.dylan.agent.kernel.definition;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;

import java.util.Objects;
import java.util.Optional;

/**
 * Capability 代码级静态结构和执行声明。
 *
 * <p>构造器执行自检：capabilityId 格式、DomainMode/AdapterRole 闭合、
 * descriptor/ContractRef/Context 声明非空无重复。
 * 不允许 enabled、角色、mask、Profile/Policy、Handler class 或 Adapter 实例字段。
 */
public final class CapabilityDefinition {

    private final String capabilityId;
    private final AgentPlanKind planKind;
    private final CapabilityRoutingDescriptor routingDescriptor;
    private final AgentDomainMode domainMode;
    private final Optional<AdapterRole> adapterRole;
    private final AgentCapabilityRiskLevel riskLevel;
    private final AgentCapabilityExecutionMode executionMode;
    private final ContractRef inputContract;
    private final ContractRef outputContract;
    private final ContextAccessDeclaration contextAccess;

    private CapabilityDefinition(Builder builder) {
        this.capabilityId = Objects.requireNonNull(builder.capabilityId);
        this.planKind = Objects.requireNonNull(builder.planKind);
        this.routingDescriptor = Objects.requireNonNull(builder.routingDescriptor);
        this.domainMode = Objects.requireNonNull(builder.domainMode);
        this.adapterRole = Optional.ofNullable(builder.adapterRole);
        this.riskLevel = Objects.requireNonNull(builder.riskLevel);
        this.executionMode = Objects.requireNonNull(builder.executionMode);
        this.inputContract = Objects.requireNonNull(builder.inputContract);
        this.outputContract = Objects.requireNonNull(builder.outputContract);
        this.contextAccess = Objects.requireNonNull(builder.contextAccess);

        // 构造器校验
        validateCapabilityId(capabilityId);
        validateDomainModeClosure();
    }

    private static void validateCapabilityId(String id) {
        if (!id.matches("[a-z][a-z0-9-]*\\.[a-z][a-z0-9-]*")) {
            throw new IllegalArgumentException(
                    "capabilityId must match [a-z][a-z0-9-]*\\.[a-z][a-z0-9-]*; got: " + id);
        }
    }

    private void validateDomainModeClosure() {
        if (domainMode == AgentDomainMode.NONE && adapterRole.isPresent()) {
            throw new IllegalArgumentException("NONE must have no adapterRole");
        }
        if ((domainMode == AgentDomainMode.OPTIONAL || domainMode == AgentDomainMode.REQUIRED)
                && adapterRole.isEmpty()) {
            throw new IllegalArgumentException(domainMode + " requires adapterRole");
        }
    }

    // ── 只读访问器 ──

    public String capabilityId() { return capabilityId; }
    public AgentPlanKind planKind() { return planKind; }
    public CapabilityRoutingDescriptor routingDescriptor() { return routingDescriptor; }
    public AgentDomainMode domainMode() { return domainMode; }
    public Optional<AdapterRole> adapterRole() { return adapterRole; }
    public AgentCapabilityRiskLevel riskLevel() { return riskLevel; }
    public AgentCapabilityExecutionMode executionMode() { return executionMode; }
    public ContractRef inputContract() { return inputContract; }
    public ContractRef outputContract() { return outputContract; }
    public ContextAccessDeclaration contextAccess() { return contextAccess; }

    // ── Builder ──

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String capabilityId;
        private AgentPlanKind planKind;
        private CapabilityRoutingDescriptor routingDescriptor;
        private AgentDomainMode domainMode;
        private AdapterRole adapterRole;
        private AgentCapabilityRiskLevel riskLevel;
        private AgentCapabilityExecutionMode executionMode;
        private ContractRef inputContract;
        private ContractRef outputContract;
        private ContextAccessDeclaration contextAccess;

        public Builder capabilityId(String v) { this.capabilityId = v; return this; }
        public Builder planKind(AgentPlanKind v) { this.planKind = v; return this; }
        public Builder routingDescriptor(CapabilityRoutingDescriptor v) { this.routingDescriptor = v; return this; }
        public Builder domainMode(AgentDomainMode v) { this.domainMode = v; return this; }
        public Builder adapterRole(AdapterRole v) { this.adapterRole = v; return this; }
        public Builder riskLevel(AgentCapabilityRiskLevel v) { this.riskLevel = v; return this; }
        public Builder executionMode(AgentCapabilityExecutionMode v) { this.executionMode = v; return this; }
        public Builder inputContract(ContractRef v) { this.inputContract = v; return this; }
        public Builder outputContract(ContractRef v) { this.outputContract = v; return this; }
        public Builder contextAccess(ContextAccessDeclaration v) { this.contextAccess = v; return this; }

        public CapabilityDefinition build() { return new CapabilityDefinition(this); }
    }
}
