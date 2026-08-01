package com.dylan.agent.service.runtime;

import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureSource;

public final class RuntimeClientException extends RuntimeException {
    private final CapabilityStatus status;
    private final String code;
    private final FailureSource source;

    private RuntimeClientException(CapabilityStatus status, String code, FailureSource source) {
        super(code, null, false, false);
        this.status = status;
        this.code = code;
        this.source = source;
    }

    public static RuntimeClientException protocolError() {
        return new RuntimeClientException(CapabilityStatus.INTERNAL_FAILURE,
                "core.runtime_protocol_error", FailureSource.CORE);
    }

    public static RuntimeClientException invalidResponse() {
        return new RuntimeClientException(CapabilityStatus.INTERNAL_FAILURE,
                "core.runtime_invalid_response", FailureSource.CORE);
    }

    public static RuntimeClientException unauthenticated() {
        return new RuntimeClientException(CapabilityStatus.UNAUTHENTICATED,
                "core.runtime_auth_context_invalid", FailureSource.CORE);
    }

    public static RuntimeClientException capacity() {
        return new RuntimeClientException(CapabilityStatus.DOWNSTREAM_FAILURE,
                "core.runtime_capacity_exceeded", FailureSource.CORE);
    }

    public static RuntimeClientException unavailable() {
        return new RuntimeClientException(CapabilityStatus.DOWNSTREAM_FAILURE,
                "downstream.runtime_unavailable", FailureSource.DOWNSTREAM);
    }

    public static RuntimeClientException failure() {
        return new RuntimeClientException(CapabilityStatus.DOWNSTREAM_FAILURE,
                "downstream.runtime_failure", FailureSource.DOWNSTREAM);
    }

    public static RuntimeClientException timeout() {
        return new RuntimeClientException(CapabilityStatus.TIMEOUT,
                "downstream.runtime_timeout", FailureSource.DOWNSTREAM);
    }

    public static RuntimeClientException connectionLost() {
        return new RuntimeClientException(CapabilityStatus.DOWNSTREAM_FAILURE,
                "downstream.runtime_connection_lost", FailureSource.DOWNSTREAM);
    }

    public CapabilityStatus status() {
        return status;
    }

    public String code() {
        return code;
    }

    public FailureSource source() {
        return source;
    }
}
