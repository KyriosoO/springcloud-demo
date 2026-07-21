package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;
import java.util.Objects;

public record DocumentEmergencyClearRequest(
        String idempotencyKey, DocumentEmergencyTargetRef target, long expectedActiveRowVersion,
        String resolutionEvidenceId, Instant deadline) {
    public DocumentEmergencyClearRequest {
        if(idempotencyKey==null||!idempotencyKey.matches("[A-Za-z0-9._:-]{8,128}"))throw new IllegalArgumentException("idempotencyKey must be a safe identifier");
        Objects.requireNonNull(target);Objects.requireNonNull(deadline);
        if(expectedActiveRowVersion<0)throw new IllegalArgumentException("expectedActiveRowVersion invalid");
        if(resolutionEvidenceId==null||!resolutionEvidenceId.matches("[A-Za-z0-9._:-]{8,128}"))throw new IllegalArgumentException("resolutionEvidenceId must be a safe identifier");
    }
    @com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}
}
