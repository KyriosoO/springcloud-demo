package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.authorization.request.CapabilityScopeSelection;
import com.dylan.agent.metadata.authorization.request.PlanningSecurityRequest;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.model.MaskType;

import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** Default D02_03 planning authorization boundary. */
public final class AuthorizationPlanningPortImpl implements AuthorizationPlanningPort {

    private final AgentMetadataStore metadataStore;
    private final EffectiveProfileCalculator profileCalculator;
    private final UserPermissionBoundary userPermissionBoundary;
    private final DelegationBoundary delegationBoundary;
    private final DomainMetadataPort domainMetadataPort;
    private final Clock clock;

    public AuthorizationPlanningPortImpl(
            AgentMetadataStore metadataStore,
            EffectiveProfileCalculator profileCalculator,
            UserPermissionBoundary userPermissionBoundary,
            DelegationBoundary delegationBoundary,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        this.metadataStore = Objects.requireNonNull(metadataStore);
        this.profileCalculator = Objects.requireNonNull(profileCalculator);
        this.userPermissionBoundary = Objects.requireNonNull(userPermissionBoundary);
        this.delegationBoundary = Objects.requireNonNull(delegationBoundary);
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public PlanningAuthorizationEvidence capture(PlanningSecurityRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        var bundle = metadataStore.current();
        String profileVersion = request.agentProfileRef().expectedVersion()
                .orElseGet(() -> bundle.activeProfileVersions().get(request.agentProfileRef().agentId()));
        if (profileVersion == null) {
            throw new IllegalStateException("profile has no active version");
        }
        var profileKey = new AgentProfileVersionKey(request.agentProfileRef().agentId(), profileVersion);
        var profile = bundle.requireProfile(profileKey);
        var policy = bundle.activePolicy();
        var effective = profileCalculator.compute(profile, policy);
        var permission = userPermissionBoundary.resolve(
                request.handle().subject(), request.handle().absoluteDeadline());
        var delegation = delegationBoundary.require(request.delegationConstraintRef());
        var scope = intersect(effective, permission, delegation);
        var domainEvidence = domainMetadataPort.validateReferences(
                DomainMetadataReferenceSet.empty(),
                request.handle().absoluteDeadline());
        return new PlanningAuthorizationEvidence(
                request.handle().requestCorrelationId(),
                subjectKey(request.handle().subject()),
                profileKey,
                bundle.bundleVersion(),
                bundle.bundleDigest(),
                policy.policyVersion(),
                permission.evidenceId(),
                permission.version(),
                request.delegationConstraintRef(),
                effective,
                scope,
                domainEvidence,
                clock.instant(),
                request.handle().absoluteDeadline());
    }

    @Override
    public void assertCurrent(PlanningAuthorizationEvidence evidence) {
        Objects.requireNonNull(evidence, "evidence must not be null");
        var bundle = metadataStore.current();
        if (!bundle.bundleVersion().equals(evidence.metadataBundleVersion())
                || !bundle.bundleDigest().equals(evidence.metadataBundleDigest())) {
            throw new IllegalStateException("metadata evidence is stale");
        }
        domainMetadataPort.assertCurrent(evidence.domainMetadataEvidence(), evidence.absoluteDeadline());
    }

    @Override
    public AuthorizationSnapshot freezeCapabilityScope(
            PlanningAuthorizationEvidence evidence,
            CapabilityScopeSelection selection) {
        assertCurrent(evidence);
        Objects.requireNonNull(selection, "selection must not be null");
        if (!selection.domainMetadataEvidence().equals(evidence.domainMetadataEvidence())) {
            throw new IllegalStateException("domain metadata evidence mismatch");
        }
        if (!evidence.planningScope().allowedCapabilityIds()
                .contains(selection.registration().capabilityId())) {
            throw new IllegalStateException("capability not allowed");
        }
        selection.selectedDomain().ifPresent(domain -> {
            if (!evidence.planningScope().allowedDomains().contains(domain)) {
                throw new IllegalStateException("domain not allowed");
            }
        });
        return new AuthorizationSnapshot(
                "auth-" + evidence.requestCorrelationId(),
                evidence.subjectRef(),
                evidence.profileKey().version(),
                evidence.policyVersion(),
                Set.of(selection.registration().capabilityId()),
                selection.selectedDomain().map(Set::of).orElseGet(Set::of),
                fieldsByDomain(evidence.planningScope()),
                clock.instant(),
                evidence.domainMetadataEvidence());
    }

    private PlanningEffectiveScope intersect(
            com.dylan.agent.metadata.profile.model.EffectiveProfile effective,
            UserPermission permission,
            com.dylan.agent.metadata.authorization.model.DelegationConstraint delegation) {
        Set<String> capabilityIds = intersect(
                intersect(effective.allowedCapabilityIds(), permission.allowedCapabilityIds()),
                delegation.allowedCapabilityIds().isEmpty()
                        ? effective.allowedCapabilityIds()
                        : delegation.allowedCapabilityIds());
        Set<String> domains = intersect(
                intersect(effective.allowedDomains(), permission.allowedDomains()),
                delegation.allowedDomains().isEmpty()
                        ? effective.allowedDomains()
                        : delegation.allowedDomains());
        return new PlanningEffectiveScope(
                capabilityIds,
                domains,
                fieldAccess(permission),
                intersect(effective.readableContextTypes(), parseContextTypes(permission.readableContextTypes())),
                intersect(effective.writableContextTypes(), parseContextTypes(permission.writableContextTypes())),
                effective.maxRiskLevel(),
                effective.maxExecutionMode(),
                effective.maxTotalDuration(),
                effective.maxRepairAttempts(),
                effective.maxPageSize(),
                effective.maxResultRows(),
                effective.maxResultBytes());
    }

    private Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> fieldAccess(UserPermission permission) {
        Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> result = new LinkedHashMap<>();
        Set<String> domains = Set.copyOf(permission.allowedDomains());
        for (String domain : domains) {
            Set<String> displayable = permission.displayableFields().getOrDefault(domain, Set.of());
            Set<String> filterable = permission.filterableFields().getOrDefault(domain, Set.of());
            Set<String> allFields = java.util.stream.Stream.concat(displayable.stream(), filterable.stream())
                    .collect(Collectors.toUnmodifiableSet());
            for (String field : allFields) {
                String key = domain + "." + field;
                result.put(new CanonicalFieldRef(domain, field),
                        new PlanningEffectiveScope.FieldAccess(
                                filterable.contains(field),
                                displayable.contains(field),
                                permission.allowedOperators().getOrDefault(key, Set.of()),
                                permission.allowedFunctions().getOrDefault(key, Set.of()),
                                Optional.of(MaskType.NONE)));
            }
        }
        return Map.copyOf(result);
    }

    private static <T> Set<T> intersect(Set<T> left, Set<T> right) {
        return left.stream().filter(right::contains).collect(Collectors.toUnmodifiableSet());
    }

    private static Set<com.dylan.agent.api.contract.runtime.common.RuntimeContextType> parseContextTypes(Set<String> values) {
        return values.stream()
                .map(String::trim)
                .map(String::toUpperCase)
                .map(com.dylan.agent.api.contract.runtime.common.RuntimeContextType::valueOf)
                .collect(Collectors.toUnmodifiableSet());
    }

    private static Map<String, Set<String>> fieldsByDomain(PlanningEffectiveScope scope) {
        Map<String, Set<String>> mutable = new LinkedHashMap<>();
        for (CanonicalFieldRef fieldRef : scope.fieldAccess().keySet()) {
            mutable.computeIfAbsent(fieldRef.domain(), ignored -> new java.util.LinkedHashSet<>())
                    .add(fieldRef.field());
        }
        return mutable.entrySet().stream().collect(Collectors.toUnmodifiableMap(
                Map.Entry::getKey,
                entry -> Set.copyOf(entry.getValue())));
    }

    private static String subjectKey(ExecutionSubjectRef subject) {
        return subject.type() + ":" + subject.id();
    }
}
