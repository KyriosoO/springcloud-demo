package com.dylan.agent.service.contract;

import java.util.Map;

public record RuntimeInvokeResponse(
        int contractVersion,
        String requestId,
        CapabilityStatus status,
        String capabilityId,
        String answerText,
        Map<String, Object> userResult,
        FailureResponse failure) {
}
