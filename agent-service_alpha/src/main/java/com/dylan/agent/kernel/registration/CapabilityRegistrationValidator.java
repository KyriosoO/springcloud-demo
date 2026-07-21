package com.dylan.agent.kernel.registration;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry;

import java.util.Collection;
import java.util.HashSet;
import java.util.Objects;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Registration 启动覆盖门禁，由 D02_01 唯一负责。
 *
 * <p>验证 ID 唯一、非空、planKind/raw subtype 一致、
 * Validator/ValidatedPlan/Handler/output 泛型闭合、ContractRef 可解析、
 * Context read/write 合法、DomainMode/AdapterRole 闭合。
 * 任一失败拒绝启动，不部分注册。
 */
@Component
public final class CapabilityRegistrationValidator {

    public void validateAll(Collection<CapabilityRegistration<?, ?, ?>> registrations,
                            ContractRegistry contracts,
                            CapabilityResourceLimitRegistry resourceContracts,
                            Set<AdapterRole> knownRoles) {
        Objects.requireNonNull(registrations);
        Objects.requireNonNull(contracts);
        Objects.requireNonNull(resourceContracts);
        Objects.requireNonNull(knownRoles);
        if (registrations.isEmpty()) {
            throw new IllegalStateException("at least one CapabilityRegistration required");
        }

        Set<String> ids = new HashSet<>();
        for (CapabilityRegistration<?, ?, ?> reg : registrations) {
            String id = reg.definition().capabilityId();
            if (id == null || !id.matches("[a-z][a-z0-9-]*\\.[a-z][a-z0-9-]*")) {
                throw new IllegalStateException("invalid capabilityId: " + id);
            }
            if (!ids.add(id)) {
                throw new IllegalStateException("duplicate capabilityId: " + id);
            }

            // planKind/raw subtype 一致性
            validatePlanKindBinding(reg);

            validateContracts(reg, contracts);
            validateResourceContract(reg, resourceContracts);

            // DomainMode/AdapterRole 闭合
            validateDomainModeClosure(reg, knownRoles);

            // Context 声明无重复——ContextAccessDeclaration 构造器已执行去重校验，
            // validator 只确认声明非 null（构造器已保证）且 write 声明的 contextType
            // 均存在于 Definition 的 ContextAccessDeclaration 中。
            Objects.requireNonNull(reg.definition().contextAccess(),
                    "contextAccess required for " + id);
            reg.definition().contextAccess().validateNoDuplicateType();

            // Routing Descriptor 完整
            Objects.requireNonNull(reg.definition().routingDescriptor());
        }
    }

    private void validateResourceContract(
            CapabilityRegistration<?, ?, ?> reg,
            CapabilityResourceLimitRegistry resourceContracts) {
        var declaration = reg.definition().resourceLimitDeclaration();
        var contract = requireResourceContract(resourceContracts, declaration);
        if (!contract.supportedDimensions().containsAll(declaration.applicableDimensions())) {
            throw new IllegalStateException("resource limit declaration dimension mismatch: "
                    + reg.definition().capabilityId());
        }
        Set<String> consumerIds = new HashSet<>();
        Set<com.dylan.agent.kernel.resource.ResourceLimitDimension> coveredDimensions = new HashSet<>();
        for (var consumer : reg.definition().resourceLimitConsumers()) {
            if (!consumerIds.add(consumer.consumerId())) {
                throw new IllegalStateException("duplicate resource limit consumer: "
                        + consumer.consumerId());
            }
            if (!consumer.contractRef().equals(declaration.contractRef())) {
                throw new IllegalStateException("resource limit consumer contract mismatch: "
                        + consumer.consumerId());
            }
            if (!declaration.applicableDimensions().containsAll(consumer.requiredDimensions())) {
                throw new IllegalStateException("resource limit consumer dimension mismatch: "
                        + consumer.consumerId());
            }
            coveredDimensions.addAll(consumer.requiredDimensions());
        }
        if (!coveredDimensions.containsAll(declaration.applicableDimensions())) {
            throw new IllegalStateException("resource limit consumer coverage incomplete: "
                    + reg.definition().capabilityId());
        }
    }

    private static <T extends com.dylan.agent.adapter.api.operation.CapabilityResourceLimit>
    com.dylan.agent.kernel.resource.CapabilityResourceLimitContract<T> requireResourceContract(
            CapabilityResourceLimitRegistry registry,
            com.dylan.agent.kernel.resource.CapabilityResourceLimitDeclaration<T> declaration) {
        var contract = registry.require(declaration.contractRef(), declaration.limitType());
        contract.validate(declaration.intrinsicUpperBound());
        return contract;
    }

    private void validatePlanKindBinding(CapabilityRegistration<?, ?, ?> reg) {
        AgentPlanKind planKind = reg.definition().planKind();
        Class<?> rawType = reg.rawPlanType();
        boolean valid = (planKind == AgentPlanKind.QUERY && rawType == QueryAgentPlan.class)
                || (planKind == AgentPlanKind.AGGREGATE && rawType == AggregateAgentPlan.class)
                || (planKind == AgentPlanKind.DOCUMENT && rawType == DocumentAgentPlan.class);
        if (!valid) {
            throw new IllegalStateException("planKind/raw subtype mismatch: "
                    + reg.definition().capabilityId());
        }
    }

    private void validateContracts(CapabilityRegistration<?, ?, ?> reg, ContractRegistry contracts) {
        var input = contracts.require(reg.definition().inputContract());
        if (!input.javaType().equals(reg.rawPlanType())) {
            throw new IllegalStateException("input ContractRef/rawPlanType mismatch: "
                    + reg.definition().capabilityId());
        }
        var output = contracts.require(reg.definition().outputContract());
        if (!output.javaType().equals(reg.outputType())) {
            throw new IllegalStateException("output ContractRef/outputType mismatch: "
                    + reg.definition().capabilityId());
        }
        reg.definition().contextAccess().reads().forEach(read -> {
            var descriptor = contracts.require(read.contractRef());
            if (!descriptor.javaType().equals(read.payloadType())) {
                throw new IllegalStateException("read Context ContractRef/payloadType mismatch: "
                        + reg.definition().capabilityId());
            }
        });
        reg.definition().contextAccess().writes().forEach(write -> {
            var descriptor = contracts.require(write.contractRef());
            if (!descriptor.javaType().equals(write.payloadType())) {
                throw new IllegalStateException("write Context ContractRef/payloadType mismatch: "
                        + reg.definition().capabilityId());
            }
        });
    }

    private void validateDomainModeClosure(CapabilityRegistration<?, ?, ?> reg, Set<AdapterRole> knownRoles) {
        AgentDomainMode mode = reg.definition().domainMode();
        if (mode == AgentDomainMode.NONE && reg.definition().adapterRole().isPresent()) {
            throw new IllegalStateException(
                    "NONE domain capability must not have adapterRole: "
                            + reg.definition().capabilityId());
        }
        if ((mode == AgentDomainMode.REQUIRED || mode == AgentDomainMode.OPTIONAL)
                && reg.definition().adapterRole().isEmpty()) {
            throw new IllegalStateException(
                    mode + " domain capability must have adapterRole: "
                            + reg.definition().capabilityId());
        }
        reg.definition().adapterRole().ifPresent(role -> {
            if (!knownRoles.contains(role)) {
                throw new IllegalStateException("unknown adapterRole for "
                        + reg.definition().capabilityId() + ": " + role);
            }
        });
    }
}
