package com.dylan.agent.kernel.registration;

import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;

import java.util.Objects;

/**
 * 唯一类型桥，封装 Java 类型擦除所需的所有受控转换。
 * Execution Core 不持有裸 wildcard Handler，不使用分散的 unchecked cast。
 *
 * <p>每个 CapabilityRegistration 构造一个对应的 bridge，
 * 构造时验证所有类型参数一致。
 */
final class TypedRegistrationInvoker<
        R extends AgentPlan,
        V extends ValidatedPlan,
        O> {

    private final CapabilityRegistration<R, V, O> registration;

    TypedRegistrationInvoker(CapabilityRegistration<R, V, O> registration) {
        this.registration = Objects.requireNonNull(registration);
    }

    ValidatedPlanHandle validate(AgentPlan raw, ExecutionValidationContext ctx) {
        R typed = castRawPlan(raw);
        V result = registration.validator().validate(typed, ctx);
        return new ValidatedPlanHandle(registration.identity(), result);
    }

    HandlerCandidate execute(ValidatedPlanHandle handle, ExecutionContext ctx) {
        Objects.requireNonNull(handle);
        if (!handle.registrationIdentity().equals(registration.identity())) {
            throw new IllegalArgumentException(
                    "handle identity mismatch: expected " + registration.identity()
                            + ", got " + handle.registrationIdentity());
        }
        if (!registration.validatedPlanType().isInstance(handle.value())) {
            throw new ClassCastException(
                    "validated plan type mismatch: expected "
                            + registration.validatedPlanType().getSimpleName());
        }
        @SuppressWarnings("unchecked")
        V validated = (V) handle.value();
        HandlerResult<O> result = registration.handler().execute(validated, ctx);
        return new HandlerCandidate(result.output(), result.contextWrites());
    }

    void validateOutput(Object output) {
        if (!registration.outputType().isInstance(output)) {
            throw new ClassCastException(
                    "handler output type mismatch: expected "
                            + registration.outputType().getSimpleName()
                            + ", got " + output.getClass().getSimpleName());
        }
    }

    @SuppressWarnings("unchecked")
    private R castRawPlan(AgentPlan raw) {
        Objects.requireNonNull(raw);
        if (!registration.rawPlanType().isInstance(raw)) {
            throw new ClassCastException(
                    "raw plan type mismatch: expected "
                            + registration.rawPlanType().getSimpleName()
                            + ", got " + raw.getClass().getSimpleName());
        }
        return (R) raw;
    }
}
