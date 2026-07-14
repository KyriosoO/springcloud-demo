package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;

import java.time.Clock;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 执行阶段授权复检边界，绝不扩大已冻结的 AuthorizationSnapshot。 */
public final class AuthorizationExecutionPortImpl implements AuthorizationExecutionPort {

    private final UserPermissionBoundary userPermissionBoundary;
    private final AgentMetadataStore metadataStore;
    private final DomainMetadataPort domainMetadataPort;
    private final Clock clock;

    public AuthorizationExecutionPortImpl(
            UserPermissionBoundary userPermissionBoundary,
            AgentMetadataStore metadataStore,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        this.userPermissionBoundary = Objects.requireNonNull(userPermissionBoundary);
        this.metadataStore = Objects.requireNonNull(metadataStore);
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public ExecutionScope recheck(AuthorizationSnapshot snapshot, InvocationHandle handle) {
        Objects.requireNonNull(snapshot, "snapshot must not be null");
        Objects.requireNonNull(handle, "handle must not be null");
        assertHandleBinding(snapshot, handle);
        var bundle = metadataStore.current();
        bundle.requireProfile(new AgentProfileVersionKey(
                snapshot.agentProfileRef().agentId(), snapshot.profileVersion()));
        var policy = bundle.policyVersionIndex().get(snapshot.policyVersion());
        if (policy == null) {
            throw new IllegalStateException("authorization snapshot policy version is unavailable");
        }
        assertNotRevoked(snapshot, policy.emergencyRevocations());
        var evidence = snapshot.domainMetadataEvidence();
        domainMetadataPort.assertCurrent(evidence, handle.absoluteDeadline());
        UserPermission current = userPermissionBoundary.resolve(handle.subject(), handle.absoluteDeadline());
        if (!current.allowedCapabilityIds().containsAll(snapshot.allowedCapabilityIds())
                || !current.allowedDomains().containsAll(snapshot.allowedDomains())
                || !coversFrozenFields(snapshot, current)
                || !coversFrozenOperatorsAndFunctions(snapshot, current)
                || !currentContextTypes(current.readableContextTypes()).containsAll(snapshot.readableContextTypes())
                || !currentContextTypes(current.writableContextTypes()).containsAll(snapshot.writableContextTypes())) {
            throw new IllegalStateException("permission recheck would shrink required scope");
        }
        var externalProcessingEvidence = snapshot.externalProcessingAuthorizationEvidence()
                .rebindPermission(current.evidenceId(), current.version());
        if (!externalProcessingEvidence.isSameOrNarrowerThan(
                snapshot.externalProcessingAuthorizationEvidence())) {
            throw new IllegalStateException("external processing authorization would expand scope");
        }
        return new ExecutionScope(
                snapshot.invocationId(),
                snapshot.requestCorrelationId(),
                snapshot.subject(),
                snapshot.owner(),
                snapshot.scope(),
                snapshot.agentProfileRef(),
                evidence,
                clock.instant(),
                snapshot.absoluteDeadline(),
                current.evidenceId(),
                current.version(),
                snapshot.policyVersion(),
                snapshot.allowedCapabilityIds(),
                snapshot.allowedDomains(),
                snapshot.allowedFields(),
                snapshot.allowedOperators(),
                snapshot.allowedFunctions(),
                snapshot.fieldMasks(),
                externalProcessingEvidence,
                snapshot.readableContextTypes(),
                snapshot.writableContextTypes(),
                snapshot.maxRiskLevel(),
                snapshot.maxExecutionMode(),
                snapshot.globalContextTtlUpperBound(),
                snapshot.resourceLimits());
    }

    private static void assertHandleBinding(AuthorizationSnapshot snapshot, InvocationHandle handle) {
        if (!snapshot.invocationId().equals(handle.invocationId())
                || !snapshot.requestCorrelationId().equals(handle.requestCorrelationId())
                || !snapshot.subject().equals(handle.subject())
                || !snapshot.owner().equals(handle.owner())
                || !snapshot.scope().scopeId().equals(handle.scope().scopeId())
                || !snapshot.agentProfileRef().equals(handle.agentProfileRef())
                || !snapshot.absoluteDeadline().equals(handle.absoluteDeadline())) {
            throw new IllegalStateException("authorization snapshot invocation binding mismatch");
        }
    }

    private static void assertNotRevoked(
            AuthorizationSnapshot snapshot,
            Set<com.dylan.agent.metadata.policy.model.EmergencyRevocation> revocations) {
        boolean revoked = revocations.stream().anyMatch(revocation -> switch (revocation.target()) {
            case PROFILE -> revocation.targetId().equals(snapshot.agentProfileRef().agentId())
                    && revocation.version().equals(snapshot.profileVersion());
            case POLICY -> revocation.targetId().equals(snapshot.policyVersion())
                    && revocation.version().equals(snapshot.policyVersion());
            case PERMISSION -> revocation.targetId().equals(snapshot.permissionEvidenceId())
                    && revocation.version().equals(snapshot.permissionVersion());
            case CAPABILITY -> snapshot.allowedCapabilityIds().contains(revocation.targetId());
        });
        if (revoked) {
            throw new IllegalStateException("authorization snapshot has been revoked");
        }
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

    private static boolean coversFrozenOperatorsAndFunctions(
            AuthorizationSnapshot snapshot,
            UserPermission current) {
        for (var entry : snapshot.allowedOperators().entrySet()) {
            if (!current.allowedOperators().getOrDefault(entry.getKey(), Set.of()).containsAll(entry.getValue())) {
                return false;
            }
        }
        for (var entry : snapshot.allowedFunctions().entrySet()) {
            if (!current.allowedFunctions().getOrDefault(entry.getKey(), Set.of()).containsAll(entry.getValue())) {
                return false;
            }
        }
        return true;
    }

    private static Set<RuntimeContextType> currentContextTypes(Set<String> values) {
        return values.stream()
                .map(RuntimeContextType::valueOf)
                .collect(java.util.stream.Collectors.toUnmodifiableSet());
    }
}
