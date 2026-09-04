package com.dylan.agent.service.contract;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;

public record RuntimeInspectResponse(
        int contractVersion,
        String requestId,
        CapabilityStatus status,
        String capabilityId,
        String answerText,
        Map<String, Object> userResult,
        FailureResponse failure,
        List<RuntimeObservation.ModelCall> modelCalls,
        List<RuntimeObservation.Plan> plans,
        List<RuntimeObservation.DownstreamCall> downstreamCalls) {

    public RuntimeInspectResponse {
        if (contractVersion != 1 || requestId == null || status == null
                || modelCalls == null || modelCalls.size() > 8
                || plans == null || plans.size() > 4
                || downstreamCalls == null || downstreamCalls.size() > 32) {
            throw new IllegalArgumentException("runtime.inspect-response-invalid");
        }
        boolean successLike = status == CapabilityStatus.SUCCESS || status == CapabilityStatus.NO_RESULT;
        if ((successLike && failure != null) || (!successLike && (failure == null || userResult != null))) {
            throw new IllegalArgumentException("runtime.inspect-response-invalid");
        }
        long uniqueSequences = Stream.of(
                        modelCalls.stream().map(RuntimeObservation.ModelCall::sequence),
                        plans.stream().map(RuntimeObservation.Plan::sequence),
                        downstreamCalls.stream().map(RuntimeObservation.DownstreamCall::sequence))
                .flatMap(stream -> stream)
                .distinct()
                .count();
        if (uniqueSequences != modelCalls.size() + plans.size() + downstreamCalls.size()) {
            throw new IllegalArgumentException("runtime.inspect-response-invalid");
        }
        userResult = userResult == null ? null : Collections.unmodifiableMap(new LinkedHashMap<>(userResult));
        modelCalls = List.copyOf(modelCalls);
        plans = List.copyOf(plans);
        downstreamCalls = List.copyOf(downstreamCalls);
    }
}
