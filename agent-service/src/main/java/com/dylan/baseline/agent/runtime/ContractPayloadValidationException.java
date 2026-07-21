package com.dylan.baseline.agent.runtime;

public final class ContractPayloadValidationException extends RuntimeException {
    public static final String CODE = "CONTRACT_PAYLOAD_INVALID";

    public ContractPayloadValidationException() {
        super(CODE);
    }
}
