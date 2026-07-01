package com.dylan.agent.kernel.registration;

import java.util.Objects;

/**
 * 当前 Registration 绑定的 ValidatedPlan handle。
 * 构造器 package-private，调用方不能伪造其他 Registration 的 handle。
 */
public final class ValidatedPlanHandle {

    private final String registrationIdentity;
    private final Object value; // V extends ValidatedPlan

    ValidatedPlanHandle(String registrationIdentity, Object value) {
        this.registrationIdentity = Objects.requireNonNull(registrationIdentity);
        this.value = Objects.requireNonNull(value);
    }

    public String registrationIdentity() { return registrationIdentity; }
    Object value() { return value; }
}
