package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.capability.document.governance.management.DocumentManagementAuthorizationContext;
import com.dylan.agent.capability.document.governance.management.DocumentManagementScope;
import com.dylan.common.security.Ed25519IntegritySupport;
import com.dylan.common.security.IntegrityKeyRef;
import com.dylan.common.security.IntegritySigningKeyProvider;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;

public final class DefaultDocumentEmergencyGateEvidenceIssuer implements DocumentEmergencyGateEvidenceIssuer {
    private final DocumentEmergencyControlReadPort emergencyReadPort;
    private final IntegritySigningKeyProvider signingKeys;
    private final IntegrityKeyRef signingKeyRef;
    private final Clock clock;
    private final Duration maximumTtl;

    public DefaultDocumentEmergencyGateEvidenceIssuer(
            DocumentEmergencyControlReadPort emergencyReadPort,
            IntegritySigningKeyProvider signingKeys,
            IntegrityKeyRef signingKeyRef,
            Clock clock,
            Duration maximumTtl) {
        this.emergencyReadPort = Objects.requireNonNull(emergencyReadPort);
        this.signingKeys = Objects.requireNonNull(signingKeys);
        this.signingKeyRef = Objects.requireNonNull(signingKeyRef);
        this.clock = Objects.requireNonNull(clock);
        this.maximumTtl = Objects.requireNonNull(maximumTtl);
        if (maximumTtl.isZero() || maximumTtl.isNegative() || maximumTtl.compareTo(Duration.ofSeconds(60)) > 0) {
            throw new IllegalArgumentException("maximumTtl must be in (0,60s]");
        }
    }

    @Override
    public DocumentEmergencyGateEvidence issueForRollout(
            DocumentEmergencyGateEvidenceIssueRequest request,
            DocumentManagementAuthorizationContext authorizationContext) {
        Objects.requireNonNull(request, "request must not be null");
        Objects.requireNonNull(authorizationContext, "authorizationContext must not be null")
                .require(DocumentManagementScope.EMERGENCY_EVIDENCE_ISSUE);
        Instant now = clock.instant();
        if (!now.isBefore(request.deadline())) throw new IllegalStateException("evidence issue deadline reached");

        List<DocumentEmergencyGateTargetBinding> targets = request.orderedTargets().stream()
                .map(DocumentEmergencyGateCanonicalizer::targetBinding)
                .sorted(Comparator.naturalOrder()).toList();
        if (targets.stream().distinct().count() != targets.size()) {
            throw new IllegalArgumentException("duplicate canonical emergency target");
        }
        DocumentEmergencyView view = emergencyReadPort.readCurrent(request.orderedTargets(), request.deadline());
        DocumentEmergencyGateStatus status = view.decisions().stream().anyMatch(
                value -> value.outcome() == DocumentEmergencyView.Outcome.FAILURE)
                ? DocumentEmergencyGateStatus.FAILURE
                : view.decisions().stream().anyMatch(value -> value.outcome() == DocumentEmergencyView.Outcome.BLOCKED)
                ? DocumentEmergencyGateStatus.BLOCKED : DocumentEmergencyGateStatus.NOT_BLOCKED;
        Instant validUntil = minimum(request.deadline(), now.plus(maximumTtl), view.validUntil());
        if (status == DocumentEmergencyGateStatus.NOT_BLOCKED && !now.isBefore(validUntil)) {
            throw new IllegalStateException("emergency view has no positive evidence lifetime");
        }
        byte[] canonical = DocumentEmergencyGateCanonicalizer.canonicalBytes(
                request.rolloutBinding(), targets, view.viewVersion(), status, now, validUntil);
        String canonicalDigest = DocumentEmergencyGateCanonicalizer.canonicalDigest(canonical);
        String signature = Ed25519IntegritySupport.signBase64Url(
                canonical, signingKeys.requireEd25519PrivateKey(signingKeyRef));
        return new DocumentEmergencyGateEvidence(
                DocumentEmergencyGateCanonicalizer.evidenceId(canonicalDigest),
                request.rolloutBinding(), targets, view.viewVersion(), status, now, validUntil,
                new DocumentEvidenceSignature(Ed25519IntegritySupport.ALGORITHM,
                        signingKeyRef.keyId(), signingKeyRef.keyVersion(), signature),
                canonicalDigest);
    }

    private static Instant minimum(Instant first, Instant second, Instant third) {
        Instant result = first.isBefore(second) ? first : second;
        return result.isBefore(third) ? result : third;
    }
}
