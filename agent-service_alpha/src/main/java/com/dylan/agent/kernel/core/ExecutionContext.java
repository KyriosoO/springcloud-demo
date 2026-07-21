package com.dylan.agent.kernel.core;

import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.invocation.model.CancellationToken;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.InvocationScope;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/**
 * Core 构建的 Handler 最小只读执行视图。
 */
public final class ExecutionContext {

    private final String invocationId;
    private final String requestCorrelationId;
    private final String capabilityId;
    private final ExecutionSubjectRef subject;
    private final ContextOwnerRef owner;
    private final InvocationScope scope;
    private final ExecutionScope executionScope;
    private final AdapterExecutionBinding adapterBinding;
    private final Instant absoluteDeadline;
    private final CancellationToken cancellation;
    private final java.util.concurrent.atomic.AtomicLong operationSequence =
            new java.util.concurrent.atomic.AtomicLong();

    ExecutionContext(
            String invocationId,
            String requestCorrelationId,
            String capabilityId,
            ExecutionSubjectRef subject,
            ContextOwnerRef owner,
            InvocationScope scope,
            ExecutionScope executionScope,
            AdapterExecutionBinding adapterBinding,
            Instant absoluteDeadline,
            CancellationToken cancellation) {
        this.invocationId = Objects.requireNonNull(invocationId);
        this.requestCorrelationId = Objects.requireNonNull(requestCorrelationId);
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.subject = Objects.requireNonNull(subject);
        this.owner = Objects.requireNonNull(owner);
        this.scope = Objects.requireNonNull(scope);
        this.executionScope = Objects.requireNonNull(executionScope);
        this.adapterBinding = adapterBinding;
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);
        this.cancellation = Objects.requireNonNull(cancellation);
    }

    public String invocationId() { return invocationId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public String capabilityId() { return capabilityId; }
    public ExecutionSubjectRef subject() { return subject; }
    public ContextOwnerRef owner() { return owner; }
    public InvocationScope scope() { return scope; }
    public ExecutionScope executionScope() { return executionScope; }
    public Optional<AdapterExecutionBinding> adapterBinding() { return Optional.ofNullable(adapterBinding); }
    public Instant absoluteDeadline() { return absoluteDeadline; }
    public CancellationToken cancellation() { return cancellation; }
    public EffectiveCapabilityResourceLimits resourceLimits() { return executionScope.resourceLimits(); }

    public CapabilityOperationContext operationContext(CapabilityOperationType operationType) {
        Objects.requireNonNull(operationType, "operationType must not be null");
        long sequence = operationSequence.incrementAndGet();
        return new CapabilityOperationContext(
                invocationId,
                requestCorrelationId,
                capabilityId,
                invocationId + ":" + sequence,
                operationType,
                absoluteDeadline,
                cancellation::isCancelled,
                resourceLimits());
    }

    /** 只验证已绑定 port 类型，不查询 Registry、不按 domain 路由。 */
    public <P extends AgentAdapterPort> P requireAdapter(Class<P> portType) {
        Objects.requireNonNull(portType);
        if (adapterBinding == null) {
            throw new IllegalStateException("no adapter binding available");
        }
        return adapterBinding.requirePort(portType);
    }
}
