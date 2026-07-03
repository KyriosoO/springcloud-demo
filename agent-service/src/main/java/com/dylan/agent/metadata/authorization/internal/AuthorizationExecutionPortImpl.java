package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;

import java.time.Clock;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 执行阶段授权复检边界，绝不扩大已冻结的 AuthorizationSnapshot。 */
public final class AuthorizationExecutionPortImpl implements AuthorizationExecutionPort {

    private final UserPermissionBoundary userPermissionBoundary;
    private final DomainMetadataPort domainMetadataPort;
    private final Clock clock;

    public AuthorizationExecutionPortImpl(
            UserPermissionBoundary userPermissionBoundary,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        this.userPermissionBoundary = Objects.requireNonNull(userPermissionBoundary);
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public ExecutionScope recheck(AuthorizationSnapshot snapshot, InvocationHandle handle) {
        Objects.requireNonNull(snapshot, "snapshot must not be null");
        Objects.requireNonNull(handle, "handle must not be null");
        if (!snapshot.subjectRef().equals(handle.subject().type() + ":" + handle.subject().id())) {
            throw new IllegalStateException("authorization snapshot subject mismatch");
        }
        var evidence = snapshot.domainMetadataEvidence()
                .orElseThrow(() -> new IllegalStateException("authorization snapshot missing domain metadata evidence"));
        domainMetadataPort.assertCurrent(evidence, handle.absoluteDeadline());
        UserPermission current = userPermissionBoundary.resolve(handle.subject(), handle.absoluteDeadline());
        if (!current.allowedCapabilityIds().containsAll(snapshot.allowedCapabilityIds())
                || !current.allowedDomains().containsAll(snapshot.allowedDomains())
                || !coversFrozenFields(snapshot, current)) {
            throw new IllegalStateException("permission recheck would shrink required scope");
        }
        return new ExecutionScope(
                snapshot.subjectRef(),
                evidence,
                clock.instant(),
                current.evidenceId(),
                current.version(),
                snapshot.policyVersion(),
                snapshot.allowedCapabilityIds(),
                snapshot.allowedDomains(),
                snapshot.allowedFields(),
                snapshot.fieldMasks(),
                handle.remaining(clock),
                snapshot.executionBudget().maxRepairAttempts(),
                snapshot.executionBudget().maxResultRows(),
                snapshot.executionBudget().maxResultBytes());
    }

    private static boolean coversFrozenFields(AuthorizationSnapshot snapshot, UserPermission current) {
        for (Map.Entry<String, Set<String>> entry : snapshot.allowedFields().entrySet()) {
            String domain = entry.getKey();
            Set<String> filterable = current.filterableFields().getOrDefault(domain, Set.of());
            Set<String> displayable = current.displayableFields().getOrDefault(domain, Set.of());
            for (String field : entry.getValue()) {
                if (!filterable.contains(field) || !displayable.contains(field)) {
                    return false;
                }
            }
        }
        return true;
    }
}
