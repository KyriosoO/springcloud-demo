package com.dylan.agent.service.contract;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public record AgentRunResponse(
        String requestId,
        String correlationId,
        CapabilityStatus status,
        List<RuntimeObservation.ModelCall> modelCalls,
        List<RuntimeObservation.Plan> plans,
        List<RuntimeObservation.DownstreamCall> downstreamCalls,
        String capabilityId,
        String answer,
        Map<String, Object> result,
        FailureResponse error) {

    public AgentRunResponse {
        if (requestId == null || correlationId == null || status == null
                || modelCalls == null || plans == null || downstreamCalls == null) {
            throw new IllegalArgumentException("agent.run-response-invalid");
        }
        boolean successLike = status == CapabilityStatus.SUCCESS || status == CapabilityStatus.NO_RESULT;
        if ((successLike && error != null) || (!successLike && (error == null || result != null))) {
            throw new IllegalArgumentException("agent.run-response-invalid");
        }
        modelCalls = List.copyOf(modelCalls);
        plans = List.copyOf(plans);
        downstreamCalls = List.copyOf(downstreamCalls);
        result = result == null ? null : Collections.unmodifiableMap(new LinkedHashMap<>(result));
    }
}
