package com.dylan.agent.service.contract;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

public record AgentQueryResponse(
        String requestId,
        String correlationId,
        CapabilityStatus status,
        String capabilityId,
        String answer,
        Map<String, Object> result,
        FailureResponse error) {

    public AgentQueryResponse {
        if (requestId == null || correlationId == null || status == null) {
            throw new IllegalArgumentException("agent.response-invalid");
        }
        boolean successLike = status == CapabilityStatus.SUCCESS || status == CapabilityStatus.NO_RESULT;
        if ((successLike && error != null) || (!successLike && (error == null || result != null))) {
            throw new IllegalArgumentException("agent.response-invalid");
        }
        result = result == null ? null : Collections.unmodifiableMap(new LinkedHashMap<>(result));
    }
}
