package com.dylan.agent.service.application;

import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureSource;

import org.springframework.http.HttpStatus;

public final class AgentPublicException extends RuntimeException {
    private final HttpStatus httpStatus;
    private final CapabilityStatus status;
    private final String code;
    private final FailureSource source;

    private AgentPublicException(
            HttpStatus httpStatus,
            CapabilityStatus status,
            String code,
            FailureSource source) {
        super(code, null, false, false);
        this.httpStatus = httpStatus;
        this.status = status;
        this.code = code;
        this.source = source;
    }

    public static AgentPublicException unauthenticated() {
        return new AgentPublicException(HttpStatus.UNAUTHORIZED, CapabilityStatus.UNAUTHENTICATED,
                "core.user_identity_required", FailureSource.CORE);
    }

    public static AgentPublicException invalidRequest() {
        return new AgentPublicException(HttpStatus.BAD_REQUEST, CapabilityStatus.INVALID_ARGUMENT,
                "core.invalid_request", FailureSource.CORE);
    }

    public static AgentPublicException ingressCapacityExceeded() {
        return new AgentPublicException(HttpStatus.TOO_MANY_REQUESTS, CapabilityStatus.DOWNSTREAM_FAILURE,
                "core.ingress_capacity_exceeded", FailureSource.CORE);
    }

    public static AgentPublicException runtimeTimeout() {
        return new AgentPublicException(HttpStatus.GATEWAY_TIMEOUT, CapabilityStatus.TIMEOUT,
                "downstream.runtime_timeout", FailureSource.DOWNSTREAM);
    }

    public static AgentPublicException internalFailure() {
        return new AgentPublicException(HttpStatus.INTERNAL_SERVER_ERROR, CapabilityStatus.INTERNAL_FAILURE,
                "core.internal_failure", FailureSource.CORE);
    }

    public HttpStatus httpStatus() {
        return httpStatus;
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
