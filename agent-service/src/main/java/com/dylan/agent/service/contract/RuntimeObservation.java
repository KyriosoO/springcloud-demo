package com.dylan.agent.service.contract;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

public final class RuntimeObservation {
    private static final Set<String> MODEL_STATUSES = Set.of("started", "succeeded", "failed");
    private static final Set<String> PLAN_TYPES = Set.of("business_query_plan", "knowledge_retrieval_plan");
    private static final Set<String> PLAN_SOURCES = Set.of("llm", "runtime_after_rewrite");
    private static final Set<String> PLAN_STATUSES = Set.of("accepted", "unsupported");
    private static final Set<String> DOWNSTREAM_STATUSES = Set.of(
            "started", "completed", "cancelled", "timeout", "transport_failure",
            "protocol_failure", "response_too_large", "tls_or_connect");

    private RuntimeObservation() {
    }

    public record ModelCall(
            int sequence,
            String taskId,
            String taskVersion,
            Map<String, Object> request,
            String status,
            String failureKind) {
        public ModelCall {
            if (sequence < 1 || !text(taskId, 64) || !text(taskVersion, 64)
                    || request == null || !MODEL_STATUSES.contains(status)) {
                throw new IllegalArgumentException("runtime.observation-model-call-invalid");
            }
            boolean succeeded = "succeeded".equals(status) && failureKind == null;
            boolean failed = "failed".equals(status) && text(failureKind, 64);
            boolean started = "started".equals(status) && failureKind == null;
            if (!succeeded && !failed && !started) {
                throw new IllegalArgumentException("runtime.observation-model-call-invalid");
            }
            request = immutable(request);
        }
    }

    public record Plan(
            int sequence,
            String type,
            String source,
            String validationStatus,
            Map<String, Object> plan) {
        public Plan {
            if (sequence < 1 || !PLAN_TYPES.contains(type) || !PLAN_SOURCES.contains(source)
                    || !PLAN_STATUSES.contains(validationStatus) || plan == null) {
                throw new IllegalArgumentException("runtime.observation-plan-invalid");
            }
            plan = immutable(plan);
        }
    }

    public record DownstreamCall(
            int sequence,
            String target,
            String operation,
            String method,
            String relativePath,
            Map<String, Object> request,
            String status,
            Integer httpStatus,
            Long durationMs) {
        public DownstreamCall {
            if (sequence < 1 || !text(target, 80) || !text(operation, 80)
                    || !("GET".equals(method) || "POST".equals(method))
                    || !text(relativePath, 256) || !relativePath.startsWith("/")
                    || request == null || !DOWNSTREAM_STATUSES.contains(status)) {
                throw new IllegalArgumentException("runtime.observation-downstream-invalid");
            }
            boolean started = "started".equals(status);
            if ((started && (httpStatus != null || durationMs != null))
                    || (!started && (durationMs == null || durationMs < 0 || durationMs > 120_000))
                    || ("completed".equals(status) && (httpStatus == null || httpStatus < 100 || httpStatus > 599))
                    || (!"completed".equals(status) && httpStatus != null)) {
                throw new IllegalArgumentException("runtime.observation-downstream-invalid");
            }
            request = immutable(request);
        }
    }

    private static boolean text(String value, int maximum) {
        return value != null && !value.isBlank() && value.length() <= maximum;
    }

    private static Map<String, Object> immutable(Map<String, Object> value) {
        return Collections.unmodifiableMap(new LinkedHashMap<>(value));
    }
}
