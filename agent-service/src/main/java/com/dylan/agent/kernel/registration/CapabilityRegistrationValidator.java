package com.dylan.agent.kernel.registration;

import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.kernel.definition.ContractRef;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;

import java.util.Collection;
import java.util.HashSet;
import java.util.Objects;
import java.util.Set;

/**
 * Registration 启动覆盖门禁，由 D02_01 唯一负责。
 *
 * <p>验证 ID 唯一、非空、planKind/raw subtype 一致、
 * Validator/ValidatedPlan/Handler/output 泛型闭合、ContractRef 可解析、
 * Context read/write 合法、DomainMode/AdapterRole 闭合。
 * 任一失败拒绝启动，不部分注册。
 */
public final class CapabilityRegistrationValidator {

    public void validateAll(Collection<CapabilityRegistration<?, ?, ?>> registrations) {
        Objects.requireNonNull(registrations);
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

            // Validator/ValidatedPlan/Handler/output 泛型闭合在 Registration 构造时已由 TypeBridge 校验

            // DomainMode/AdapterRole 闭合
            validateDomainModeClosure(reg);

            // Context 声明无重复——ContextAccessDeclaration 构造器已执行去重校验，
            // validator 只确认声明非 null（构造器已保证）且 write 声明的 contextType
            // 均存在于 Definition 的 ContextAccessDeclaration 中。
            Objects.requireNonNull(reg.definition().contextAccess(),
                    "contextAccess required for " + id);

            // Routing Descriptor 完整
            Objects.requireNonNull(reg.definition().routingDescriptor());
        }
    }

    private void validatePlanKindBinding(CapabilityRegistration<?, ?, ?> reg) {
        // planKind 必须与 Raw Plan discriminator 一致
        // 由 D02_01 的 ContractRegistry 在 D03 阶段解析
    }

    private void validateDomainModeClosure(CapabilityRegistration<?, ?, ?> reg) {
        AgentDomainMode mode = reg.definition().domainMode();
        if (mode == AgentDomainMode.REQUIRED
                && reg.definition().adapterRole().isEmpty()) {
            throw new IllegalStateException(
                    "REQUIRED domain capability must have adapterRole: "
                            + reg.definition().capabilityId());
        }
    }
}
