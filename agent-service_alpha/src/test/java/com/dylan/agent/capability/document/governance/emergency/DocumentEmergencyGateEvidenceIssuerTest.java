package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.capability.document.governance.management.DocumentManagementAuthorizationContext;
import com.dylan.agent.capability.document.governance.management.DocumentManagementScope;
import com.dylan.common.security.Ed25519IntegritySupport;
import com.dylan.common.security.IntegrityKeyRef;
import org.junit.jupiter.api.Test;

import java.security.KeyPairGenerator;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentEmergencyGateEvidenceIssuerTest {
    private static final String DIGEST_A = "a".repeat(64);
    private static final String DIGEST_B = "b".repeat(64);
    private static final String DIGEST_C = "c".repeat(64);

    @Test
    void signsExactNotBlockedRolloutEvidence() throws Exception {
        Instant now = Instant.parse("2026-07-14T08:00:00Z");
        var keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        var keyRef = new IntegrityKeyRef("document-governance", "v1");
        DocumentEmergencyTargetRef target = new DocumentEmergencyTargetRef.CorpusTarget(
                new DocumentCorpusKey("employee", "policy"));
        var binding = DocumentEmergencyGateCanonicalizer.targetBinding(target);
        DocumentEmergencyControlReadPort readPort = (targets, deadline) -> new DocumentEmergencyView(
                "DEV-test", List.of(new DocumentEmergencyView.Decision(
                binding.targetType().name(), binding.targetKeyDigest(),
                DocumentEmergencyView.Outcome.NOT_BLOCKED, null)), now, now.plusSeconds(10), DIGEST_A);
        var issuer = new DefaultDocumentEmergencyGateEvidenceIssuer(
                readPort, ignored -> keyPair.getPrivate(), keyRef,
                Clock.fixed(now, ZoneOffset.UTC), Duration.ofSeconds(10));

        DocumentEmergencyGateEvidence evidence = issuer.issueForRollout(
                new DocumentEmergencyGateEvidenceIssueRequest(
                        new DocumentEmergencyRolloutBinding(
                                "INDEX_TARGET", DIGEST_A, DIGEST_B, DIGEST_C, "report-1"),
                        List.of(target), now.plusSeconds(20)),
                authorization(now, Set.of(DocumentManagementScope.EMERGENCY_EVIDENCE_ISSUE)));

        byte[] canonical = DocumentEmergencyGateCanonicalizer.canonicalBytes(
                evidence.rolloutBinding(), evidence.orderedTargets(), evidence.emergencyViewVersion(),
                evidence.status(), evidence.issuedAt(), evidence.validUntil());
        assertThat(evidence.status()).isEqualTo(DocumentEmergencyGateStatus.NOT_BLOCKED);
        assertThat(evidence.validUntil()).isEqualTo(now.plusSeconds(10));
        assertThat(evidence.canonicalDigest())
                .isEqualTo(DocumentEmergencyGateCanonicalizer.canonicalDigest(canonical));
        assertThat(Ed25519IntegritySupport.verifyBase64Url(
                canonical, evidence.signature().signatureBase64Url(), keyPair.getPublic())).isTrue();
    }

    @Test
    void rejectsCallerWithoutIssueScopeBeforeReadingState() throws Exception {
        Instant now = Instant.parse("2026-07-14T08:00:00Z");
        var keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        var issuer = new DefaultDocumentEmergencyGateEvidenceIssuer(
                (targets, deadline) -> { throw new AssertionError("read must not occur"); },
                ignored -> keyPair.getPrivate(), new IntegrityKeyRef("document-governance", "v1"),
                Clock.fixed(now, ZoneOffset.UTC), Duration.ofSeconds(10));
        var target = new DocumentEmergencyTargetRef.CorpusTarget(new DocumentCorpusKey("employee", "policy"));

        assertThatThrownBy(() -> issuer.issueForRollout(
                new DocumentEmergencyGateEvidenceIssueRequest(
                        new DocumentEmergencyRolloutBinding(
                                "INDEX_TARGET", DIGEST_A, DIGEST_B, DIGEST_C, "report-1"),
                        List.of(target), now.plusSeconds(20)), authorization(now, Set.of())))
                .isInstanceOf(SecurityException.class);
    }

    private static DocumentManagementAuthorizationContext authorization(
            Instant now, Set<DocumentManagementScope> scopes) {
        return new DocumentManagementAuthorizationContext(
                "release-tooling", "actor-safe", scopes, now, "d".repeat(64));
    }
}
