package com.dylan.agent.service.contract;

public record FailureResponse(String code, FailureSource source) {

    public FailureResponse {
        if (code == null || code.length() > 128
                || !code.matches("[a-z][a-z0-9_-]*(\\.[a-z][a-z0-9_-]*)+")) {
            throw new IllegalArgumentException("agent.failure-invalid");
        }
        if (source == null) {
            throw new IllegalArgumentException("agent.failure-invalid");
        }
    }
}
