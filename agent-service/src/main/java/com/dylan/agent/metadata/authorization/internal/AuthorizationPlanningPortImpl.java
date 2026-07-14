package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit;
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
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.kernel.resource.CapabilityResourceLimitDeclaration;
import com.dylan.agent.kernel.resource.EffectiveCapabilityResourceLimits;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContribution;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitResolver;
import com.dylan.agent.metadata.authorization.resource.ResourceLimitSource;

import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/** D02_03 默认规划授权边界。 */
public final class AuthorizationPlanningPortImpl implements AuthorizationPlanningPort {

    private final AgentMetadataStore metadataStore;
    private final EffectiveProfileCalculator profileCalculator;
    private final UserPermissionBoundary userPermissionBoundary;
    private final CapabilityResourceLimitResolver resourceLimitResolver;
    private final DomainMetadataPort domainMetadataPort;
    private final Clock clock;
    private final ExternalProcessingAuthorizationEvidenceFactory externalProcessingEvidenceFactory =
            new ExternalProcessingAuthorizationEvidenceFactory();

    public AuthorizationPlanningPortImpl(
            AgentMetadataStore metadataStore,
            EffectiveProfileCalculator profileCalculator,
            UserPermissionBoundary userPermissionBoundary,
            CapabilityResourceLimitResolver resourceLimitResolver,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        this.metadataStore = Objects.requireNonNull(metadataStore);
        this.profileCalculator = Objects.requireNonNull(profileCalculator);
        this.userPermissionBoundary = Objects.requireNonNull(userPermissionBoundary);
        this.resourceLimitResolver = Objects.requireNonNull(resourceLimitResolver);
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
        if (!com.dylan.agent.metadata.authorization.model.DelegationConstraintRef.CHAT_ALL
                .equals(request.delegationConstraintRef())) {
            throw new IllegalStateException("current phase only permits CHAT_ALL delegation constraint");
        }
        var scope = intersect(effective, permission, policy);
        var domainEvidence = domainMetadataPort.validateReferences(
                DomainMetadataReferenceSet.empty(),
                request.handle().absoluteDeadline());
        return new PlanningAuthorizationEvidence(
                request.handle().invocationId(),
                request.handle().requestCorrelationId(),
                request.handle().subject(),
                request.handle().owner(),
                (com.dylan.agent.invocation.model.ConversationScope) request.handle().scope(),
                com.dylan.agent.shared.ref.AgentProfileRef.of(profileKey.agentId(), profileKey.version()),
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
                policy.globalContextTtlUpperBound(),
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
        Set<String> frozenDomains = selection.selectedDomain().map(Set::of).orElseGet(Set::of);
        Map<String, Set<String>> frozenFields = fieldsByDomain(evidence.planningScope(), frozenDomains);
        return new AuthorizationSnapshot(
                "auth-" + evidence.requestCorrelationId(),
                evidence.invocationId(),
                evidence.requestCorrelationId(),
                evidence.subject(),
                evidence.owner(),
                evidence.scope(),
                evidence.agentProfileRef(),
                evidence.policyVersion(),
                evidence.permissionEvidenceId(),
                evidence.permissionVersion(),
                evidence.delegationConstraintRef(),
                Set.of(selection.registration().capabilityId()),
                frozenDomains,
                frozenFields,
                operatorsByField(evidence.planningScope(), frozenDomains),
                functionsByField(evidence.planningScope(), frozenDomains),
                fieldMasks(evidence.planningScope(), frozenDomains),
                evidence.planningScope().externalProcessingAuthorizationEvidence()
                        .narrowTo(frozenDomains, frozenFields),
                evidence.planningScope().readableContextTypes(),
                evidence.planningScope().writableContextTypes(),
                evidence.planningScope().maxRiskLevel(),
                evidence.planningScope().maxExecutionMode(),
                evidence.globalContextTtlUpperBound(),
                clock.instant(),
                evidence.absoluteDeadline(),
                evidence.domainMetadataEvidence(),
                resolveResourceLimits(evidence, selection));
    }

    private EffectiveCapabilityResourceLimits resolveResourceLimits(
            PlanningAuthorizationEvidence evidence,
            CapabilityScopeSelection selection) {
        var declaration = selection.registration().registration().definition().resourceLimitDeclaration();
        return resolveTypedResourceLimits(evidence, selection, declaration);
    }

    private <T extends com.dylan.agent.adapter.api.operation.CapabilityResourceLimit>
    EffectiveCapabilityResourceLimits resolveTypedResourceLimits(
            PlanningAuthorizationEvidence evidence,
            CapabilityScopeSelection selection,
            CapabilityResourceLimitDeclaration<T> typed) {
        var profile = evidence.planningScope().resourceLimitContributions().require(
                ResourceLimitSource.PROFILE, typed.contractRef(), typed.limitType());
        var policy = evidence.planningScope().resourceLimitContributions().require(
                ResourceLimitSource.POLICY, typed.contractRef(), typed.limitType());
        var contributions = java.util.List.<CapabilityResourceLimitContribution<?>>of(
                profile,
                policy,
                new CapabilityResourceLimitContribution<>(
                        ResourceLimitSource.PERMISSION, typed.contractRef(), typed.limitType(),
                        typed.intrinsicUpperBound(), evidence.permissionEvidenceId()));
        return resourceLimitResolver.resolve(
                evidence.invocationId(),
                evidence.requestCorrelationId(),
                selection.registration().registrationIdentity(),
                evidence.evidenceDigest(),
                typed,
                contributions,
                clock.instant());
    }

    private PlanningEffectiveScope intersect(
            com.dylan.agent.metadata.profile.model.EffectiveProfile effective,
            UserPermission permission,
            com.dylan.agent.metadata.policy.model.AgentPolicySnapshot policy) {
        Set<String> capabilityIds = intersect(
                effective.allowedCapabilityIds(), permission.allowedCapabilityIds());
        Set<String> domains = intersect(
                effective.allowedDomains(), permission.allowedDomains());
        Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> fields =
                fieldAccess(permission, domains, policy.domainSecurityConstraints());
        return new PlanningEffectiveScope(
                capabilityIds,
                domains,
                fields,
                externalProcessingEvidenceFactory.create(
                        policy.policyVersion(), permission, domains, fields, policy.domainSecurityConstraints()),
                intersect(effective.readableContextTypes(), parseContextTypes(permission.readableContextTypes())),
                intersect(effective.writableContextTypes(), parseContextTypes(permission.writableContextTypes())),
                effective.maxRiskLevel(),
                effective.maxExecutionMode(),
                effective.planningBudgetLimits(),
                effective.resourceLimitContributions());
    }

    private Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> fieldAccess(
            UserPermission permission,
            Set<String> allowedDomains,
            Map<String, DomainSecurityConstraints> domainSecurityConstraints) {
        Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> result = new LinkedHashMap<>();
        for (String domain : allowedDomains) {
            Set<String> displayable = permission.displayableFields().getOrDefault(domain, Set.of());
            Set<String> filterable = permission.filterableFields().getOrDefault(domain, Set.of());
            Set<String> allFields = java.util.stream.Stream.concat(displayable.stream(), filterable.stream())
                    .collect(Collectors.toUnmodifiableSet());
            for (String field : allFields) {
                String key = domain + "." + field;
                CanonicalFieldRef fieldRef = new CanonicalFieldRef(domain, field);
                DomainSecurityConstraints.FieldSecurityConstraint policyConstraint =
                        Optional.ofNullable(domainSecurityConstraints.get(domain))
                                .map(DomainSecurityConstraints::fields)
                                .map(fields -> fields.get(fieldRef))
                                .orElse(null);
                boolean filterAllowed = filterable.contains(field);
                boolean displayAllowed = displayable.contains(field);
                Set<AgentOperator> allowedOperators = permission.allowedOperators().getOrDefault(key, Set.of());
                Set<String> allowedFunctions = permission.allowedFunctions().getOrDefault(key, Set.of());
                Optional<MaskType> requiredMask = Optional.of(MaskType.NONE);
                if (policyConstraint != null) {
                    filterAllowed = filterAllowed && policyConstraint.filterAllowed();
                    displayAllowed = displayAllowed && policyConstraint.displayAllowed();
                    allowedOperators = intersect(allowedOperators, policyConstraint.allowedOperators());
                    allowedFunctions = intersect(allowedFunctions, policyConstraint.allowedFunctions());
                    requiredMask = Optional.of(policyConstraint.requiredMask().orElse(MaskType.NONE));
                }
                // ExecutionScope 只有单一 allowedFields 集合，任一维度被收紧时按 fail closed 删除字段。
                if (filterAllowed && displayAllowed) {
                    result.put(fieldRef,
                            new PlanningEffectiveScope.FieldAccess(
                                    true,
                                    true,
                                    allowedOperators,
                                    allowedFunctions,
                                    requiredMask));
                }
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

    private static Map<String, Set<String>> fieldsByDomain(PlanningEffectiveScope scope, Set<String> frozenDomains) {
        Map<String, Set<String>> mutable = new LinkedHashMap<>();
        for (CanonicalFieldRef fieldRef : scope.fieldAccess().keySet()) {
            if (!frozenDomains.contains(fieldRef.domain())) {
                continue;
            }
            mutable.computeIfAbsent(fieldRef.domain(), ignored -> new java.util.LinkedHashSet<>())
                    .add(fieldRef.field());
        }
        return mutable.entrySet().stream().collect(Collectors.toUnmodifiableMap(
                Map.Entry::getKey,
                entry -> Set.copyOf(entry.getValue())));
    }

    private static Map<String, Set<AgentOperator>> operatorsByField(
            PlanningEffectiveScope scope,
            Set<String> frozenDomains) {
        return scope.fieldAccess().entrySet().stream()
                .filter(entry -> frozenDomains.contains(entry.getKey().domain()))
                .collect(Collectors.toUnmodifiableMap(
                        entry -> maskKey(entry.getKey().domain(), entry.getKey().field()),
                        entry -> entry.getValue().allowedOperators()));
    }

    private static Map<String, Set<String>> functionsByField(
            PlanningEffectiveScope scope,
            Set<String> frozenDomains) {
        return scope.fieldAccess().entrySet().stream()
                .filter(entry -> frozenDomains.contains(entry.getKey().domain()))
                .collect(Collectors.toUnmodifiableMap(
                        entry -> maskKey(entry.getKey().domain(), entry.getKey().field()),
                        entry -> entry.getValue().allowedFunctions()));
    }

    private static Map<String, MaskType> fieldMasks(PlanningEffectiveScope scope, Set<String> frozenDomains) {
        Map<String, MaskType> masks = new LinkedHashMap<>();
        for (Map.Entry<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> entry
                : scope.fieldAccess().entrySet()) {
            CanonicalFieldRef fieldRef = entry.getKey();
            if (!frozenDomains.contains(fieldRef.domain())) {
                continue;
            }
            MaskType maskType = entry.getValue().requiredMask().orElse(MaskType.NONE);
            if (maskType != MaskType.NONE) {
                masks.put(maskKey(fieldRef.domain(), fieldRef.field()), maskType);
            }
        }
        return Map.copyOf(masks);
    }

    private static String maskKey(String domain, String field) {
        return domain + "." + field;
    }

}
