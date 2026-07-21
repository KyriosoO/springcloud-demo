package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalDiagnostics;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentObservabilitySupportTest {

    @Test
    void recordsLowCardinalityDocumentMetrics() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        DocumentObservabilitySupport support = new DocumentObservabilitySupport(registry);

        support.recordRetrieval("policy_document", "HYBRID", "SUCCESS", Duration.ofMillis(25));
        support.recordProvider("generation", "ANSWER", "FALLBACK");
        support.recordResultSecurity("FILTERED");
        support.recordRevocationHit("DOMAIN", "LOCAL_BLOCKLIST");

        assertThat(registry.counter(
                "agent_document_retrieval_total",
                "domain", "policy_document",
                "mode", "HYBRID",
                "result", "SUCCESS").count()).isEqualTo(1.0);
        assertThat(registry.counter(
                "agent_document_provider_total",
                "providerType", "generation",
                "operation", "ANSWER",
                "result", "FALLBACK").count()).isEqualTo(1.0);
    }

    @Test
    void rejectsForbiddenHighCardinalityOrSensitiveMetricTags() {
        assertThatThrownBy(() -> DocumentObservabilitySupport.requireLowCardinality(Map.of(
                "documentId", "doc-1",
                "result", "SUCCESS")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("documentId");
        assertThatThrownBy(() -> DocumentObservabilitySupport.requireLowCardinality(Map.of(
                "queryText", "查询休假政策")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("queryText");
    }

    @Test
    void recordsChannelRrfRerankMetrics() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        DocumentObservabilitySupport support = new DocumentObservabilitySupport(registry);
        AdapterDocumentRetrievalDiagnostics diagnostics = new AdapterDocumentRetrievalDiagnostics();
        diagnostics.setChannelHitCounts(Map.of("BM25", 3, "DENSE_VECTOR", 2));
        diagnostics.setFusedCandidateCount(5);
        diagnostics.setDedupedCandidateCount(3);
        diagnostics.setRerankStatus("SKIPPED");

        support.recordRetrievalDiagnostics("policy_document", "HYBRID", diagnostics);

        assertThat(registry.counter(
                "agent_document_channel_hit_total",
                "domain", "policy_document",
                "mode", "HYBRID",
                "channel", "BM25").count()).isEqualTo(3.0);
        assertThat(registry.counter(
                "agent_document_channel_hit_total",
                "domain", "policy_document",
                "mode", "HYBRID",
                "channel", "DENSE_VECTOR").count()).isEqualTo(2.0);
        assertThat(registry.find("agent_document_dedup_reduction_ratio").summary().count()).isEqualTo(1L);
        assertThat(registry.counter(
                "agent_document_rerank_total",
                "domain", "policy_document",
                "status", "SKIPPED").count()).isEqualTo(1.0);
    }
}
