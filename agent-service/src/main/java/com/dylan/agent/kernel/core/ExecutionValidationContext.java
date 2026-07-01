package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.InvocationScope;

import java.time.Instant;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Core 构建的 Plan Validator 最小只读视图。
 */
public final class ExecutionValidationContext {

    private final String capabilityId;
    private final AgentPlanKind planKind;
    private final AgentDomainMode domainMode;
    private final Object executionScope; // ExecutionScope after D02_03
    private final Object domainProjection; // ExecutionValidationProjection after D02_03
    private final Object adapterBinding; // AdapterExecutionBinding, nullable
    private final List<Object> contextSnapshots; // List<ContextSnapshot>
    private final Instant absoluteDeadline;
    private final Object cancellation; // CancellationToken

    ExecutionValidationContext(
            String capabilityId,
            AgentPlanKind planKind,
            AgentDomainMode domainMode,
            Object executionScope,
            Object domainProjection,
            Object adapterBinding,
            List<Object> contextSnapshots,
            Instant absoluteDeadline,
            Object cancellation) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.planKind = Objects.requireNonNull(planKind);
        this.domainMode = Objects.requireNonNull(domainMode);
        this.executionScope = Objects.requireNonNull(executionScope);
        this.domainProjection = Objects.requireNonNull(domainProjection);
        this.adapterBinding = adapterBinding; // nullable
        this.contextSnapshots = List.copyOf(contextSnapshots != null ? contextSnapshots : List.of());
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);
        this.cancellation = cancellation;
    }

    public String capabilityId() { return capabilityId; }
    public AgentPlanKind planKind() { return planKind; }
    public AgentDomainMode domainMode() { return domainMode; }
    public Object executionScope() { return executionScope; }
    public Object domainProjection() { return domainProjection; }
    public Optional<Object> adapterBinding() { return Optional.ofNullable(adapterBinding); }
    public List<Object> contextSnapshots() { return contextSnapshots; }
    public Instant absoluteDeadline() { return absoluteDeadline; }
    public Object cancellation() { return cancellation; }
}
