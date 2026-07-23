package com.dylan.esquery.document.governance.emergency;

import java.time.Instant;
import java.util.List;

public record DocumentEmergencyGateEvidence(
        String evidenceId, DocumentEmergencyRolloutBinding rolloutBinding,
        List<DocumentEmergencyGateTargetBinding> orderedTargets, String emergencyViewVersion,
        DocumentEmergencyGateStatus status, Instant issuedAt, Instant validUntil,
        DocumentEvidenceSignature signature, String canonicalDigest) {
    public DocumentEmergencyGateEvidence { orderedTargets=orderedTargets==null?null:List.copyOf(orderedTargets); }
}
