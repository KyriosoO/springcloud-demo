package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalDiagnostics;
import io.micrometer.core.instrument.MeterRegistry;

import java.time.Duration;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

/** 文档能力低基数指标封装，禁止把敏感或高基数字段作为标签。 */
public final class DocumentObservabilitySupport {

    private static final Set<String> FORBIDDEN_TAGS = Set.of(
            "userId",
            "subjectRef",
            "documentId",
            "chunkId",
            "queryText",
            "sourceUri",
            "validationDigest",
            "permissionEvidenceId",
            "taskId",
            "token");

    private final MeterRegistry meterRegistry;

    public DocumentObservabilitySupport(MeterRegistry meterRegistry) {
        this.meterRegistry = Objects.requireNonNull(meterRegistry, "meterRegistry must not be null");
    }

    public void recordRetrieval(String domain, String mode, String result, Duration duration) {
        requireLowCardinality(Map.of("domain", domain, "mode", mode, "result", result));
        meterRegistry.counter("agent_document_retrieval_total",
                "domain", safe(domain),
                "mode", safe(mode),
                "result", safe(result)).increment();
        meterRegistry.timer("agent_document_retrieval_duration",
                "domain", safe(domain),
                "mode", safe(mode)).record(duration);
    }

    public void recordProvider(String providerType, String operation, String result) {
        requireLowCardinality(Map.of("providerType", providerType, "operation", operation, "result", result));
        meterRegistry.counter("agent_document_provider_total",
                "providerType", safe(providerType),
                "operation", safe(operation),
                "result", safe(result)).increment();
    }

    public void recordResultSecurity(String decision) {
        requireLowCardinality(Map.of("decision", decision));
        meterRegistry.counter("agent_document_result_security_total", "decision", safe(decision)).increment();
    }

    public void recordRevocationHit(String target, String source) {
        requireLowCardinality(Map.of("target", target, "source", source));
        meterRegistry.counter("agent_document_revocation_hit_total",
                "target", safe(target),
                "source", safe(source)).increment();
    }

    public void recordRetrievalDiagnostics(
            String domain,
            String mode,
            AdapterDocumentRetrievalDiagnostics diagnostics) {
        if (diagnostics == null) {
            return;
        }
        if (diagnostics.getChannelHitCounts() != null) {
            diagnostics.getChannelHitCounts().forEach((channel, count) -> {
                requireLowCardinality(Map.of("domain", domain, "mode", mode, "channel", channel));
                meterRegistry.counter("agent_document_channel_hit_total",
                        "domain", safe(domain),
                        "mode", safe(mode),
                        "channel", safe(channel)).increment(Math.max(0, count == null ? 0 : count));
            });
        }
        if (diagnostics.getFusedCandidateCount() != null
                && diagnostics.getDedupedCandidateCount() != null
                && diagnostics.getFusedCandidateCount() > 0) {
            double ratio = 1.0d - Math.min(
                    diagnostics.getFusedCandidateCount(),
                    Math.max(0, diagnostics.getDedupedCandidateCount()))
                    / (double) diagnostics.getFusedCandidateCount();
            meterRegistry.summary("agent_document_dedup_reduction_ratio",
                    "domain", safe(domain),
                    "mode", safe(mode)).record(ratio);
        }
        if (diagnostics.getRerankStatus() != null && !diagnostics.getRerankStatus().isBlank()) {
            requireLowCardinality(Map.of("domain", domain, "status", diagnostics.getRerankStatus()));
            meterRegistry.counter("agent_document_rerank_total",
                    "domain", safe(domain),
                    "status", safe(diagnostics.getRerankStatus())).increment();
        }
    }

    public static void requireLowCardinality(Map<String, String> tags) {
        tags.keySet().forEach(tag -> {
            if (FORBIDDEN_TAGS.contains(tag)) {
                throw new IllegalArgumentException("forbidden document metric tag: " + tag);
            }
        });
    }

    private static String safe(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }
}
