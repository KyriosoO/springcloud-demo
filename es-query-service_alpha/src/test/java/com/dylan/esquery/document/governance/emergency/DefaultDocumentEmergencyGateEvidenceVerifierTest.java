package com.dylan.esquery.document.governance.emergency;

import com.dylan.common.security.Ed25519IntegritySupport;
import org.junit.jupiter.api.Test;

import java.security.KeyPairGenerator;
import java.time.Duration;
import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DefaultDocumentEmergencyGateEvidenceVerifierTest {
    private static final String A="a".repeat(64),B="b".repeat(64),C="c".repeat(64),D="d".repeat(64);

    @Test
    void verifiesExactSignedEvidenceAndRejectsDifferentExpectedRollout() throws Exception {
        Instant now=Instant.parse("2026-07-14T08:00:00Z");
        var keys=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        var rollout=new DocumentEmergencyRolloutBinding("INDEX_TARGET",A,B,C,"report-1");
        var targets=List.of(new DocumentEmergencyGateTargetBinding(DocumentEmergencyTargetType.CORPUS,D));
        var unsigned=new DocumentEmergencyGateEvidence(A,rollout,targets,"DEV-test",DocumentEmergencyGateStatus.NOT_BLOCKED,
                now,now.plusSeconds(10),new DocumentEvidenceSignature("Ed25519","document-governance","v1","x".repeat(86)),B);
        byte[] canonical=DocumentEmergencyGateCanonicalizer.canonicalBytes(unsigned);
        String digest=DocumentEmergencyGateCanonicalizer.canonicalDigest(canonical);
        var evidence=new DocumentEmergencyGateEvidence(DocumentEmergencyGateCanonicalizer.evidenceId(digest),rollout,targets,
                "DEV-test",DocumentEmergencyGateStatus.NOT_BLOCKED,now,now.plusSeconds(10),
                new DocumentEvidenceSignature("Ed25519","document-governance","v1",
                        Ed25519IntegritySupport.signBase64Url(canonical,keys.getPrivate())),digest);
        var verifier=new DefaultDocumentEmergencyGateEvidenceVerifier(ref->keys.getPublic(),Duration.ofSeconds(1));

        assertThat(verifier.verify(evidence,rollout,targets,now).code())
                .isEqualTo(DocumentEmergencyGateVerificationCode.VERIFIED);
        assertThat(verifier.verify(evidence,
                new DocumentEmergencyRolloutBinding("INDEX_TARGET",A,B,D,"report-1"),targets,now).code())
                .isEqualTo(DocumentEmergencyGateVerificationCode.ROLLOUT_BINDING_MISMATCH);
    }

    @Test
    void rejectsTamperedSignatureAndExpiredEvidence() throws Exception {
        Instant issued=Instant.parse("2026-07-14T08:00:00Z");
        var keys=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        var rollout=new DocumentEmergencyRolloutBinding("INDEX_TARGET",A,B,C,"report-1");
        var targets=List.of(new DocumentEmergencyGateTargetBinding(DocumentEmergencyTargetType.CORPUS,D));
        var evidence=evidence(issued,rollout,targets,keys);
        var verifier=new DefaultDocumentEmergencyGateEvidenceVerifier(ref->keys.getPublic(),Duration.ZERO);

        var tampered=new DocumentEmergencyGateEvidence(evidence.evidenceId(),evidence.rolloutBinding(),evidence.orderedTargets(),
                evidence.emergencyViewVersion(),evidence.status(),evidence.issuedAt(),evidence.validUntil(),
                new DocumentEvidenceSignature("Ed25519","document-governance","v1","A"+evidence.signature().signatureBase64Url().substring(1)),
                evidence.canonicalDigest());
        assertThat(verifier.verify(tampered,rollout,targets,issued).code())
                .isEqualTo(DocumentEmergencyGateVerificationCode.SIGNATURE_INVALID);
        assertThat(verifier.verify(evidence,rollout,targets,issued.plusSeconds(10)).code())
                .isEqualTo(DocumentEmergencyGateVerificationCode.EXPIRED);
    }

    @Test
    void rejectsSignedEvidenceWhoseLifetimeExceedsProtocolMaximum() throws Exception {
        Instant issued=Instant.parse("2026-07-14T08:00:00Z");
        var keys=KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        var rollout=new DocumentEmergencyRolloutBinding("INDEX_TARGET",A,B,C,"report-1");
        var targets=List.of(new DocumentEmergencyGateTargetBinding(DocumentEmergencyTargetType.CORPUS,D));
        var placeholder=new DocumentEmergencyGateEvidence(A,rollout,targets,"DEV-test",DocumentEmergencyGateStatus.NOT_BLOCKED,
                issued,issued.plusSeconds(61),new DocumentEvidenceSignature("Ed25519","document-governance","v1","x".repeat(86)),B);
        byte[] canonical=DocumentEmergencyGateCanonicalizer.canonicalBytes(placeholder);
        String digest=DocumentEmergencyGateCanonicalizer.canonicalDigest(canonical);
        var evidence=new DocumentEmergencyGateEvidence(DocumentEmergencyGateCanonicalizer.evidenceId(digest),rollout,targets,
                "DEV-test",DocumentEmergencyGateStatus.NOT_BLOCKED,issued,issued.plusSeconds(61),
                new DocumentEvidenceSignature("Ed25519","document-governance","v1",
                        Ed25519IntegritySupport.signBase64Url(canonical,keys.getPrivate())),digest);
        var verifier=new DefaultDocumentEmergencyGateEvidenceVerifier(ref->keys.getPublic(),Duration.ZERO);

        assertThat(verifier.verify(evidence,rollout,targets,issued).code())
                .isEqualTo(DocumentEmergencyGateVerificationCode.MALFORMED);
    }

    private static DocumentEmergencyGateEvidence evidence(Instant issued,DocumentEmergencyRolloutBinding rollout,
                                                            List<DocumentEmergencyGateTargetBinding> targets,
                                                            java.security.KeyPair keys){
        var placeholder=new DocumentEmergencyGateEvidence(A,rollout,targets,"DEV-test",DocumentEmergencyGateStatus.NOT_BLOCKED,
                issued,issued.plusSeconds(10),new DocumentEvidenceSignature("Ed25519","document-governance","v1","x".repeat(86)),B);
        byte[] canonical=DocumentEmergencyGateCanonicalizer.canonicalBytes(placeholder);
        String digest=DocumentEmergencyGateCanonicalizer.canonicalDigest(canonical);
        return new DocumentEmergencyGateEvidence(DocumentEmergencyGateCanonicalizer.evidenceId(digest),rollout,targets,
                "DEV-test",DocumentEmergencyGateStatus.NOT_BLOCKED,issued,issued.plusSeconds(10),
                new DocumentEvidenceSignature("Ed25519","document-governance","v1",Ed25519IntegritySupport.signBase64Url(canonical,keys.getPrivate())),digest);
    }
}
