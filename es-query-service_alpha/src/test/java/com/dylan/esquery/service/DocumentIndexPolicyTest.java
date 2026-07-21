package com.dylan.esquery.service;

import com.dylan.esquery.config.EsQueryProperties;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentIndexPolicyTest {

    @Test
    void matchesConfiguredDocumentIndexPrefixes() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        properties.setDocumentIndexPrefixes(List.of("agent-doc-", "kb-"));
        DocumentIndexPolicy policy = new DocumentIndexPolicy(properties);

        assertThat(policy.isDocumentIndex("agent-doc-policy")).isTrue();
        assertThat(policy.isDocumentIndex("kb-public")).isTrue();
        assertThat(policy.isDocumentIndex("orders")).isFalse();
    }

    @Test
    void ignoresBlankConfiguredPrefixesAndKeepsDefault() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        properties.setDocumentIndexPrefixes(List.of("  "));
        DocumentIndexPolicy policy = new DocumentIndexPolicy(properties);

        assertThat(policy.isDocumentIndex("agent-doc-policy")).isTrue();
        assertThat(policy.isDocumentIndex("orders")).isFalse();
    }
}
