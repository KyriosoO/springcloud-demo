package com.dylan.agent.service.contract;

import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.annotation.JsonCreator;

public enum CapabilityStatus {
    SUCCESS("success"),
    NO_RESULT("no_result"),
    UNSUPPORTED("unsupported"),
    INVALID_ARGUMENT("invalid_argument"),
    UNAUTHENTICATED("unauthenticated"),
    FORBIDDEN("forbidden"),
    TIMEOUT("timeout"),
    DOWNSTREAM_FAILURE("downstream_failure"),
    MODEL_EGRESS_DENIED("model_egress_denied"),
    INTERNAL_FAILURE("internal_failure");

    private final String wireValue;

    CapabilityStatus(String wireValue) {
        this.wireValue = wireValue;
    }

    @JsonValue
    public String wireValue() {
        return wireValue;
    }

    @JsonCreator
    public static CapabilityStatus fromWireValue(String value) {
        for (CapabilityStatus status : values()) {
            if (status.wireValue.equals(value)) {
                return status;
            }
        }
        throw new IllegalArgumentException("agent.status-invalid");
    }
}
