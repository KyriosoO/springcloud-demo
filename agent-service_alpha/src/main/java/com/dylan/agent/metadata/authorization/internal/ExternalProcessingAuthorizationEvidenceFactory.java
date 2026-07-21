package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.metadata.authorization.model.ExternalProcessingAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.ExternalProcessingFieldRule;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.model.MaskType;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** 构造 Policy 与当前 Permission 求交后的外部处理授权证据。 */
public final class ExternalProcessingAuthorizationEvidenceFactory {

    public ExternalProcessingAuthorizationEvidence create(
            String policyVersion,
            UserPermission permission,
            Set<String> allowedDomains,
            Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> fieldAccess,
            Map<String, DomainSecurityConstraints> domainSecurityConstraints) {
        Objects.requireNonNull(permission, "permission must not be null");
        Objects.requireNonNull(allowedDomains, "allowedDomains must not be null");
        Objects.requireNonNull(fieldAccess, "fieldAccess must not be null");
        Objects.requireNonNull(domainSecurityConstraints, "domainSecurityConstraints must not be null");

        Map<String, Set<CapabilityOperationType>> domainPurposes = new LinkedHashMap<>();
        for (String domain : allowedDomains.stream().sorted().toList()) {
            DomainSecurityConstraints constraint = domainSecurityConstraints.get(domain);
            if (constraint != null && !constraint.externalProcessingPurposes().isEmpty()) {
                domainPurposes.put(domain, constraint.externalProcessingPurposes());
            }
        }

        Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules = new LinkedHashMap<>();
        fieldAccess.entrySet().stream()
                .sorted(Map.Entry.comparingByKey(
                        java.util.Comparator.comparing(CanonicalFieldRef::domain)
                                .thenComparing(CanonicalFieldRef::field)))
                .forEach(entry -> addFieldRule(entry, domainPurposes, domainSecurityConstraints, fieldRules));

        String policyDigest = policyDigest(policyVersion, domainSecurityConstraints);
        String permissionDigest = ExternalProcessingAuthorizationEvidence.permissionDigest(
                permission.evidenceId(), permission.version(), domainPurposes.keySet(), fieldRules.keySet());
        return new ExternalProcessingAuthorizationEvidence(
                domainPurposes, fieldRules, policyDigest, permissionDigest);
    }

    private static String policyDigest(
            String policyVersion,
            Map<String, DomainSecurityConstraints> constraints) {
        Map<String, Set<CapabilityOperationType>> policyDomains = constraints.entrySet().stream()
                .filter(entry -> !entry.getValue().externalProcessingPurposes().isEmpty())
                .collect(Collectors.toUnmodifiableMap(
                        Map.Entry::getKey,
                        entry -> entry.getValue().externalProcessingPurposes()));
        Map<CanonicalFieldRef, ExternalProcessingFieldRule> policyFields = new LinkedHashMap<>();
        constraints.values().forEach(domain -> domain.fields().forEach((field, rule) -> {
            Set<CapabilityOperationType> purposes = rule.externalProcessingPurposes().stream()
                    .filter(policyDomains.getOrDefault(field.domain(), Set.of())::contains)
                    .collect(Collectors.toUnmodifiableSet());
            if (!purposes.isEmpty()) {
                policyFields.put(field, new ExternalProcessingFieldRule(
                        field, rule.classification(), rule.requiredMask().orElse(MaskType.NONE), purposes));
            }
        }));
        return ExternalProcessingAuthorizationEvidence.policyDigest(
                policyVersion, policyDomains, policyFields);
    }

    private static void addFieldRule(
            Map.Entry<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> entry,
            Map<String, Set<CapabilityOperationType>> domainPurposes,
            Map<String, DomainSecurityConstraints> constraints,
            Map<CanonicalFieldRef, ExternalProcessingFieldRule> target) {
        CanonicalFieldRef field = entry.getKey();
        DomainSecurityConstraints domainConstraint = constraints.get(field.domain());
        if (domainConstraint == null) return;
        DomainSecurityConstraints.FieldSecurityConstraint policyField = domainConstraint.fields().get(field);
        if (policyField == null) return;
        Set<CapabilityOperationType> purposes = policyField.externalProcessingPurposes().stream()
                .filter(domainPurposes.getOrDefault(field.domain(), Set.of())::contains)
                .collect(Collectors.toUnmodifiableSet());
        if (purposes.isEmpty()) return;
        MaskType mask = entry.getValue().requiredMask().orElse(MaskType.NONE);
        target.put(field, new ExternalProcessingFieldRule(
                field, policyField.classification(), mask, purposes));
    }
}
