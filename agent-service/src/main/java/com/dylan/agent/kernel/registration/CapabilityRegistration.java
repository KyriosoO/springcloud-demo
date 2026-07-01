package com.dylan.agent.kernel.registration;

import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.validator.CapabilityPlanValidator;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.kernel.handler.CapabilityHandler;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;

import java.util.Objects;

/**
 * 不可变执行注册单元，由 D02_01 唯一负责。
 *
 * <p>聚合 Definition、Raw Plan type、Validator、Validated Plan type、
 * Handler、Output type 和唯一类型桥。构造后所有组件只读。
 *
 * @param <R> Raw Plan subtype (e.g. QueryAgentPlan)
 * @param <V> Validated Plan type
 * @param <O> Handler output type
 */
public final class CapabilityRegistration<
        R extends AgentPlan,
        V extends ValidatedPlan,
        O> {

    private final CapabilityDefinition definition;
    private final Class<R> rawPlanType;
    private final CapabilityPlanValidator<R, V> validator;
    private final Class<V> validatedPlanType;
    private final CapabilityHandler<V, O> handler;
    private final Class<O> outputType;
    private final TypedRegistrationInvoker<R, V, O> invoker;
    private final String identity;

    public CapabilityRegistration(
            CapabilityDefinition definition,
            Class<R> rawPlanType,
            CapabilityPlanValidator<R, V> validator,
            Class<V> validatedPlanType,
            CapabilityHandler<V, O> handler,
            Class<O> outputType) {
        this.definition = Objects.requireNonNull(definition);
        this.rawPlanType = Objects.requireNonNull(rawPlanType);
        this.validator = Objects.requireNonNull(validator);
        this.validatedPlanType = Objects.requireNonNull(validatedPlanType);
        this.handler = Objects.requireNonNull(handler);
        this.outputType = Objects.requireNonNull(outputType);
        this.invoker = new TypedRegistrationInvoker<>(this);
        this.identity = computeIdentity();
    }

    private String computeIdentity() {
        return "CapabilityRegistration{" +
                "capabilityId=" + definition.capabilityId() +
                ", planKind=" + definition.planKind() +
                ", domainMode=" + definition.domainMode() +
                ", rawPlan=" + rawPlanType.getSimpleName() +
                ", validatedPlan=" + validatedPlanType.getSimpleName() +
                ", handler=" + handler.getClass().getSimpleName() +
                ", output=" + outputType.getSimpleName() +
                '}';
    }

    // ── 只读访问器 ──

    public CapabilityDefinition definition() { return definition; }
    public Class<R> rawPlanType() { return rawPlanType; }
    public CapabilityPlanValidator<R, V> validator() { return validator; }
    public Class<V> validatedPlanType() { return validatedPlanType; }
    public CapabilityHandler<V, O> handler() { return handler; }
    public Class<O> outputType() { return outputType; }

    /** 稳定摘要，不包含实例地址。 */
    public String identity() { return identity; }

    /**
     * 唯一类型桥：注册级受控 cast + Validator。
     * 返回当前 Registration 绑定的 ValidatedPlanHandle，不能伪造其他 Registration 的 handle。
     */
    public ValidatedPlanHandle validateRaw(AgentPlan raw, ExecutionValidationContext ctx) {
        return invoker.validate(raw, ctx);
    }

    /** 唯一类型桥：注册级受控 cast + Handler。 */
    public HandlerCandidate executeValidated(ValidatedPlanHandle handle, ExecutionContext ctx) {
        return invoker.execute(handle, ctx);
    }

    /** 运行时 output type 校验。 */
    public void validateOutput(Object output) {
        invoker.validateOutput(output);
    }
}
