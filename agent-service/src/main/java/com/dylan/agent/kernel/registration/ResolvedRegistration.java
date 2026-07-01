package com.dylan.agent.kernel.registration;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;

import java.util.Objects;

/**
 * Planning 按 capabilityId 解析的不可变 Registration 引用。
 * 放入 ExecutablePlanningResult，执行阶段不重新查询 Registry。
 */
public final class ResolvedRegistration {

    private final String capabilityId;
    private final AgentPlanKind planKind;
    private final String registrationIdentity;
    private final CapabilityRegistration<?, ?, ?> registration;

    ResolvedRegistration(String capabilityId, AgentPlanKind planKind,
                         String registrationIdentity,
                         CapabilityRegistration<?, ?, ?> registration) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.planKind = Objects.requireNonNull(planKind);
        this.registrationIdentity = Objects.requireNonNull(registrationIdentity);
        this.registration = Objects.requireNonNull(registration);
    }

    public String capabilityId() { return capabilityId; }
    public AgentPlanKind planKind() { return planKind; }
    public String registrationIdentity() { return registrationIdentity; }
    public CapabilityRegistration<?, ?, ?> registration() { return registration; }

    public void validateIdentity() {
        if (!registration.identity().equals(registrationIdentity)) {
            throw new IllegalStateException(
                    "registration identity mismatch: " + registrationIdentity);
        }
    }
}
