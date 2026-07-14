package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;

import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/** 当前 Invocation 内唯一的 Provider 外发允许决策。 */
public final class DocumentProviderOutboundPolicyDecision {
    private final CapabilityOperationType operationType;
    private final DocumentCorpusKey corpusKey;
    private final String authorizationBindingDigest;
    private final String policyEvidenceDigest;
    private final String permissionEvidenceDigest;
    private final String profileProjectionDigest;
    private final ResourceLimitReference resourceLimitReference;
    private final List<DocumentProviderFieldRuleDecision> orderedFieldRules;
    private final Instant validUntil;
    private final String canonicalDigest;

    public DocumentProviderOutboundPolicyDecision(
            CapabilityOperationType operationType,
            DocumentCorpusKey corpusKey,
            String authorizationBindingDigest,
            String policyEvidenceDigest,
            String permissionEvidenceDigest,
            String profileProjectionDigest,
            ResourceLimitReference resourceLimitReference,
            List<DocumentProviderFieldRuleDecision> orderedFieldRules,
            Instant validUntil,
            DocumentProviderOutboundPolicyCanonicalizer canonicalizer) {
        this.operationType = Objects.requireNonNull(operationType, "operationType must not be null");
        this.corpusKey = Objects.requireNonNull(corpusKey, "corpusKey must not be null");
        this.authorizationBindingDigest = requireDigest(authorizationBindingDigest, "authorizationBindingDigest");
        this.policyEvidenceDigest = requireDigest(policyEvidenceDigest, "policyEvidenceDigest");
        this.permissionEvidenceDigest = requireDigest(permissionEvidenceDigest, "permissionEvidenceDigest");
        this.profileProjectionDigest = requireDigest(profileProjectionDigest, "profileProjectionDigest");
        this.resourceLimitReference = Objects.requireNonNull(resourceLimitReference, "resourceLimitReference must not be null");
        this.orderedFieldRules = Objects.requireNonNull(orderedFieldRules, "orderedFieldRules must not be null").stream()
                .map(rule -> Objects.requireNonNull(rule, "field rule must not be null"))
                .sorted(Comparator.comparing((DocumentProviderFieldRuleDecision rule) -> rule.field().domain())
                .thenComparing(rule -> rule.field().field()))
                .toList();
        if (this.orderedFieldRules.stream().map(DocumentProviderFieldRuleDecision::field).distinct().count()
                != this.orderedFieldRules.size()) {
            throw new IllegalArgumentException("duplicate document provider field rule");
        }
        this.validUntil = Objects.requireNonNull(validUntil, "validUntil must not be null");
        this.canonicalDigest = Objects.requireNonNull(canonicalizer, "canonicalizer must not be null").canonicalDigest(this);
    }

    public CapabilityOperationType operationType() { return operationType; }
    public DocumentCorpusKey corpusKey() { return corpusKey; }
    public String authorizationBindingDigest() { return authorizationBindingDigest; }
    public String policyEvidenceDigest() { return policyEvidenceDigest; }
    public String permissionEvidenceDigest() { return permissionEvidenceDigest; }
    public String profileProjectionDigest() { return profileProjectionDigest; }
    public ResourceLimitReference resourceLimitReference() { return resourceLimitReference; }
    public List<DocumentProviderFieldRuleDecision> orderedFieldRules() { return orderedFieldRules; }
    public Instant validUntil() { return validUntil; }
    public String canonicalDigest() { return canonicalDigest; }

    private static String requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256 hex");
        }
        return value;
    }
}
