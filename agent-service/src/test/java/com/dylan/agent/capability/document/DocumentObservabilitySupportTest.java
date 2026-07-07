package com.dylan.agent.capability.document;

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
}
