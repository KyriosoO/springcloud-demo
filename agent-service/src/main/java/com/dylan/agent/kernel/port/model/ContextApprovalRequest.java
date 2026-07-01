package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.context.model.ContextSnapshot;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;

public final class ContextApprovalRequest {

    private final InvocationHandle handle;
    private final ResolvedRegistration registration;
    private final ExecutionScope executionScope;
    private final List<ContextSnapshot> consumedSnapshots;
    private final Map<RuntimeContextType, ContextSnapshot> consumedSnapshotsByType;
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
        this.consumedSnapshotsByType = indexByContextType(this.consumedSnapshots);
        this.now = Objects.requireNonNull(now);
    }

    public InvocationHandle handle() { return handle; }
    public ResolvedRegistration registration() { return registration; }
    public ExecutionScope executionScope() { return executionScope; }
    public List<ContextSnapshot> consumedSnapshots() { return consumedSnapshots; }
    public Map<RuntimeContextType, ContextSnapshot> consumedSnapshotsByType() { return consumedSnapshotsByType; }
    public Optional<ContextSnapshot> consumedSnapshot(RuntimeContextType contextType) {
        return Optional.ofNullable(consumedSnapshotsByType.get(Objects.requireNonNull(contextType)));
    }
    public Instant now() { return now; }

    private static Map<RuntimeContextType, ContextSnapshot> indexByContextType(List<ContextSnapshot> snapshots) {
        Map<RuntimeContextType, ContextSnapshot> indexed = new LinkedHashMap<>();
        for (ContextSnapshot snapshot : snapshots) {
            Objects.requireNonNull(snapshot, "consumed snapshot must not be null");
            ContextSnapshot previous = indexed.putIfAbsent(snapshot.contextType(), snapshot);
            if (previous != null) {
                throw new IllegalArgumentException("duplicate consumed contextType: " + snapshot.contextType());
            }
        }
        return Map.copyOf(indexed);
    }
}
