package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.ExternalProcessingFieldRule;

import java.time.Instant;
import java.time.Clock;
import java.util.ArrayList;
import java.util.List;

/** 四类 Document Provider operation 的唯一外发策略解释器。 */
public final class DocumentProviderOutboundPolicyDecisionFactory {
    private final DocumentProviderOutboundPolicyCanonicalizer canonicalizer;
    private final Clock clock;

    public DocumentProviderOutboundPolicyDecisionFactory(
            DocumentProviderOutboundPolicyCanonicalizer canonicalizer,
            Clock clock) {
        this.canonicalizer = java.util.Objects.requireNonNull(canonicalizer, "canonicalizer must not be null");
        this.clock = java.util.Objects.requireNonNull(clock, "clock must not be null");
    }

    public DocumentProviderOutboundPolicyDecisionResult create(
            CapabilityOperationType type,
            ExecutionScope scope,
            DocumentCorpusKey corpus,
            DocumentFeaturePolicy feature,
            DocumentProviderIntendedFieldView fieldView,
            String profileProjectionDigest,
            Instant absoluteDeadline) {
        if (type == null || !DocumentProviderOperationTypes.ALL.contains(type)) {
            return denied(DocumentProviderOutboundPolicyDenialCode.INVALID_OPERATION);
        }
        if (scope == null || corpus == null || feature == null || fieldView == null
                || profileProjectionDigest == null || absoluteDeadline == null) {
            return denied(DocumentProviderOutboundPolicyDenialCode.SCOPE_MISSING);
        }
        if (!scope.recheckedAt().isBefore(scope.absoluteDeadline())
                || !clock.instant().isBefore(scope.absoluteDeadline())) {
            return denied(DocumentProviderOutboundPolicyDenialCode.SCOPE_EXPIRED);
        }
        if (!scope.absoluteDeadline().equals(absoluteDeadline)) {
            return denied(DocumentProviderOutboundPolicyDenialCode.INVOCATION_BINDING_MISMATCH);
        }
        if (feature == DocumentFeaturePolicy.DISABLED) {
            return denied(DocumentProviderOutboundPolicyDenialCode.FEATURE_DISABLED);
        }
        if (!scope.allowedDomains().contains(corpus.domain())) {
            return denied(DocumentProviderOutboundPolicyDenialCode.CORPUS_NOT_ALLOWED);
        }
        var evidence = scope.externalProcessingAuthorizationEvidence();
        if (evidence == null || !evidence.allowsDomain(corpus.domain(), type)) {
            return denied(DocumentProviderOutboundPolicyDenialCode.PURPOSE_NOT_ALLOWED);
        }
        if (!profileProjectionDigest.matches("[0-9a-f]{64}")) {
            return denied(DocumentProviderOutboundPolicyDenialCode.EVIDENCE_BINDING_MISMATCH);
        }

        List<DocumentProviderFieldRuleDecision> decisions = new ArrayList<>();
        for (var field : fieldView.orderedFields()) {
            if (!corpus.domain().equals(field.domain())
                    || !scope.allowedFields().getOrDefault(field.domain(), java.util.Set.of()).contains(field.field())) {
                return denied(DocumentProviderOutboundPolicyDenialCode.FIELD_NOT_ALLOWED);
            }
            ExternalProcessingFieldRule rule;
            try {
                rule = evidence.requireFieldRule(field, type);
            } catch (IllegalArgumentException ex) {
                return denied(DocumentProviderOutboundPolicyDenialCode.CLASSIFICATION_PURPOSE_NOT_ALLOWED);
            }
            if (rule.classification() == null) {
                return denied(DocumentProviderOutboundPolicyDenialCode.CLASSIFICATION_MISSING);
            }
            decisions.add(new DocumentProviderFieldRuleDecision(
                    field, rule.classification(), rule.maskType()));
        }

        try {
            return new DocumentProviderOutboundPolicyAllowed(new DocumentProviderOutboundPolicyDecision(
                    type,
                    corpus,
                    evidence.canonicalDigest(),
                    evidence.policyEvidenceDigest(),
                    evidence.permissionEvidenceDigest(),
                    profileProjectionDigest,
                    scope.resourceLimits().reference(),
                    decisions,
                    absoluteDeadline,
                    canonicalizer));
        } catch (IllegalArgumentException ex) {
            return denied(DocumentProviderOutboundPolicyDenialCode.EVIDENCE_BINDING_MISMATCH);
        }
    }

    private static DocumentProviderOutboundPolicyDenied denied(
            DocumentProviderOutboundPolicyDenialCode code) {
        return new DocumentProviderOutboundPolicyDenied(code);
    }
}
