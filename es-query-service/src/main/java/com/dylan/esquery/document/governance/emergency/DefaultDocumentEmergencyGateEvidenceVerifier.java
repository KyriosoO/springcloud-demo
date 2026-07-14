package com.dylan.esquery.document.governance.emergency;

import com.dylan.common.security.Ed25519IntegritySupport;
import com.dylan.common.security.IntegrityKeyRef;
import com.dylan.common.security.IntegrityVerificationKeyProvider;

import java.time.Duration;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;

public final class DefaultDocumentEmergencyGateEvidenceVerifier implements DocumentEmergencyGateEvidenceVerifier {
    private final IntegrityVerificationKeyProvider verificationKeys;
    private final Duration allowedClockSkew;

    public DefaultDocumentEmergencyGateEvidenceVerifier(
            IntegrityVerificationKeyProvider verificationKeys, Duration allowedClockSkew) {
        this.verificationKeys=Objects.requireNonNull(verificationKeys);
        this.allowedClockSkew=Objects.requireNonNull(allowedClockSkew);
        if(allowedClockSkew.isNegative()||allowedClockSkew.compareTo(Duration.ofSeconds(5))>0)throw new IllegalArgumentException("allowedClockSkew must be in [0,5s]");
    }

    @Override
    public DocumentEmergencyGateVerification verify(
            DocumentEmergencyGateEvidence evidence, DocumentEmergencyRolloutBinding expectedRollout,
            List<DocumentEmergencyGateTargetBinding> expectedTargets, Instant now) {
        if(!wellFormed(evidence,expectedRollout,expectedTargets,now))return result(DocumentEmergencyGateVerificationCode.MALFORMED,evidence);
        if(!Ed25519IntegritySupport.ALGORITHM.equals(evidence.signature().algorithm()))return result(DocumentEmergencyGateVerificationCode.ALGORITHM_NOT_ALLOWED,evidence);
        byte[] canonical=DocumentEmergencyGateCanonicalizer.canonicalBytes(evidence);
        if(!evidence.canonicalDigest().equals(DocumentEmergencyGateCanonicalizer.canonicalDigest(canonical))
                ||!evidence.evidenceId().equals(DocumentEmergencyGateCanonicalizer.evidenceId(evidence.canonicalDigest())))return result(DocumentEmergencyGateVerificationCode.MALFORMED,evidence);
        java.security.PublicKey key;
        try{key=verificationKeys.requireEd25519PublicKey(new IntegrityKeyRef(evidence.signature().keyId(),evidence.signature().keyVersion()));}
        catch(RuntimeException ex){return result(DocumentEmergencyGateVerificationCode.KEY_NOT_TRUSTED,evidence);}
        if(!Ed25519IntegritySupport.verifyBase64Url(canonical,evidence.signature().signatureBase64Url(),key))return result(DocumentEmergencyGateVerificationCode.SIGNATURE_INVALID,evidence);
        if(evidence.issuedAt().isAfter(now.plus(allowedClockSkew)))return result(DocumentEmergencyGateVerificationCode.NOT_YET_VALID,evidence);
        if(!now.isBefore(evidence.validUntil()))return result(DocumentEmergencyGateVerificationCode.EXPIRED,evidence);
        if(!evidence.rolloutBinding().equals(expectedRollout))return result(DocumentEmergencyGateVerificationCode.ROLLOUT_BINDING_MISMATCH,evidence);
        List<DocumentEmergencyGateTargetBinding> orderedExpected=expectedTargets.stream().sorted().toList();
        if(!evidence.orderedTargets().equals(orderedExpected))return result(DocumentEmergencyGateVerificationCode.TARGET_SET_MISMATCH,evidence);
        if(evidence.status()==DocumentEmergencyGateStatus.BLOCKED)return result(DocumentEmergencyGateVerificationCode.STATUS_BLOCKED,evidence);
        if(evidence.status()==DocumentEmergencyGateStatus.FAILURE)return result(DocumentEmergencyGateVerificationCode.STATUS_FAILURE,evidence);
        return result(DocumentEmergencyGateVerificationCode.VERIFIED,evidence);
    }

    private static boolean wellFormed(DocumentEmergencyGateEvidence evidence,
                                      DocumentEmergencyRolloutBinding expectedRollout,
                                      List<DocumentEmergencyGateTargetBinding> expectedTargets,Instant now){
        if(evidence==null||expectedRollout==null||expectedTargets==null||now==null||evidence.rolloutBinding()==null
                ||evidence.orderedTargets()==null||evidence.orderedTargets().isEmpty()||evidence.orderedTargets().size()>200
                ||evidence.emergencyViewVersion()==null||!evidence.emergencyViewVersion().matches("[A-Za-z0-9._-]{1,128}")
                ||evidence.status()==null||evidence.issuedAt()==null||evidence.validUntil()==null||evidence.signature()==null
                ||evidence.canonicalDigest()==null||!evidence.canonicalDigest().matches("[0-9a-f]{64}")
                ||evidence.evidenceId()==null||!evidence.evidenceId().matches("[0-9a-f]{64}"))return false;
        return evidence.orderedTargets().equals(evidence.orderedTargets().stream().sorted().toList())
                &&new HashSet<>(evidence.orderedTargets()).size()==evidence.orderedTargets().size();
    }

    private static DocumentEmergencyGateVerification result(DocumentEmergencyGateVerificationCode code,DocumentEmergencyGateEvidence evidence){
        String prefix=evidence!=null&&evidence.evidenceId()!=null&&evidence.evidenceId().length()>=12?evidence.evidenceId().substring(0,12):"unbound";
        return new DocumentEmergencyGateVerification(code,"EGE-"+code.name()+"-"+prefix);
    }
}
