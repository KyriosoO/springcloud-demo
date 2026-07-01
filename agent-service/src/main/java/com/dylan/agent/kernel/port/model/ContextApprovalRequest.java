package com.dylan.agent.kernel.port.model;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.context.model.ContextSnapshot;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

public final class ContextApprovalRequest {

    private final InvocationHandle handle;
    private final ResolvedRegistration registration;
    private final ExecutionScope executionScope;
    private final List<ContextSnapshot> consumedSnapshots;
    private final Instant now;

    public ContextApprovalRequest(InvocationHandle handle,
                                  ResolvedRegistration registration,
                                  ExecutionScope executionScope,
                                  List<ContextSnapshot> consumedSnapshots,
                                  Instant now) {
        this.handle = Objects.requireNonNull(handle);
        this.registration = Objects.requireNonNull(registration);
        this.executionScope = Objects.requireNonNull(executionScope);
        this.consumedSnapshots = List.copyOf(consumedSnapshots == null ? List.of() : consumedSnapshots);
        this.now = Objects.requireNonNull(now);
    }

    public InvocationHandle handle() { return handle; }
    public ResolvedRegistration registration() { return registration; }
    public ExecutionScope executionScope() { return executionScope; }
    public List<ContextSnapshot> consumedSnapshots() { return consumedSnapshots; }
    public Instant now() { return now; }
}
