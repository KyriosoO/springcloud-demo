package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.invocation.model.CancellationToken;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.context.model.ContextSnapshot;

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
    private final ExecutionScope executionScope;
    private final ExecutionValidationProjection domainProjection;
    private final AdapterExecutionBinding adapterBinding;
    private final List<ContextSnapshot> contextSnapshots;
    private final Instant absoluteDeadline;
    private final CancellationToken cancellation;

    ExecutionValidationContext(
            String capabilityId,
            AgentPlanKind planKind,
            AgentDomainMode domainMode,
            ExecutionScope executionScope,
            ExecutionValidationProjection domainProjection,
            AdapterExecutionBinding adapterBinding,
            List<ContextSnapshot> contextSnapshots,
            Instant absoluteDeadline,
            CancellationToken cancellation) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.planKind = Objects.requireNonNull(planKind);
        this.domainMode = Objects.requireNonNull(domainMode);
        this.executionScope = Objects.requireNonNull(executionScope);
        this.domainProjection = Objects.requireNonNull(domainProjection);
        this.adapterBinding = adapterBinding; // nullable
        this.contextSnapshots = List.copyOf(contextSnapshots != null ? contextSnapshots : List.of());
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);
        this.cancellation = Objects.requireNonNull(cancellation);
    }

    public String capabilityId() { return capabilityId; }
    public AgentPlanKind planKind() { return planKind; }
    public AgentDomainMode domainMode() { return domainMode; }
    public ExecutionScope executionScope() { return executionScope; }
    public EffectiveCapabilityResourceLimits resourceLimits() { return executionScope.resourceLimits(); }
    public ExecutionValidationProjection domainProjection() { return domainProjection; }
    public Optional<AdapterExecutionBinding> adapterBinding() { return Optional.ofNullable(adapterBinding); }
    public List<ContextSnapshot> contextSnapshots() { return contextSnapshots; }
    public Instant absoluteDeadline() { return absoluteDeadline; }
    public CancellationToken cancellation() { return cancellation; }
}
