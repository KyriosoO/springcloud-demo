package com.dylan.agent.capability.document.governance.emergency;

import java.time.Instant;
import java.util.Objects;

public record DocumentEmergencyDisableRequest(
        String idempotencyKey, DocumentEmergencyTargetRef target, long expectedRowVersion,
        DocumentEmergencyReasonCode reasonCode, Instant deadline) {
    public DocumentEmergencyDisableRequest {
        if(idempotencyKey==null||!idempotencyKey.matches("[A-Za-z0-9._:-]{8,128}"))throw new IllegalArgumentException("idempotencyKey must be a safe identifier");
        Objects.requireNonNull(target);Objects.requireNonNull(reasonCode);Objects.requireNonNull(deadline);
        if(expectedRowVersion < -1)throw new IllegalArgumentException("expectedRowVersion invalid");
    }
    @com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}
}
