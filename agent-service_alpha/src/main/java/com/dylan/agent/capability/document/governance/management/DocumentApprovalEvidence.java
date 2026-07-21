package com.dylan.agent.capability.document.governance.management;

import java.time.Instant;

public record DocumentApprovalEvidence(
        String evidenceRef,String approverSafeRef,DocumentApprovalKind kind,
        Instant validUntil,String canonicalDigest) {
    public DocumentApprovalEvidence {
        if(evidenceRef==null||evidenceRef.isBlank()||approverSafeRef==null||approverSafeRef.isBlank())throw new IllegalArgumentException("approval safe refs required");
        java.util.Objects.requireNonNull(kind);java.util.Objects.requireNonNull(validUntil);
        if(canonicalDigest==null||!canonicalDigest.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("approval canonicalDigest must be SHA-256 hex");
    }
}
