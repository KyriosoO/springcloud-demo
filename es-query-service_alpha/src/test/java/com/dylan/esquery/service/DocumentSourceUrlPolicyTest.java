package com.dylan.esquery.service;

import com.dylan.esquery.config.EsQueryProperties;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentSourceUrlPolicyTest {

    @Test
    void acceptsConfiguredMockHost() {
        DocumentSourceUrlPolicy policy = policy(List.of("document-platform"));

        assertThatCode(() -> policy.validate("http://document-platform/internal/chunks"))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsNonAllowlistedHost() {
        DocumentSourceUrlPolicy policy = policy(List.of("document-platform"));

        assertThatThrownBy(() -> policy.validate("https://evil.example/internal/chunks"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not allowed");
    }

    @Test
    void rejectsUrlWithUserInfo() {
        DocumentSourceUrlPolicy policy = policy(List.of("document-platform"));

        assertThatThrownBy(() -> policy.validate("http://user:secret@document-platform/internal/chunks"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("userInfo");
    }

    @Test
    void rejectsReservedQueryParameterInSourceUrl() {
        DocumentSourceUrlPolicy policy = policy(List.of("document-platform"));

        assertThatThrownBy(() -> policy.validate("http://document-platform/internal/chunks?cursor=override"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("reserved parameter");
    }

    @Test
    void rejectsNonHttpScheme() {
        DocumentSourceUrlPolicy policy = policy(List.of("document-platform"));

        assertThatThrownBy(() -> policy.validate("file:///tmp/chunks.json"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("scheme");
    }

    @Test
    void rejectsEmptyAllowlist() {
        DocumentSourceUrlPolicy policy = policy(List.of());

        assertThatThrownBy(() -> policy.validate("http://document-platform/internal/chunks"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("document-source-allowed-hosts");
    }

    private DocumentSourceUrlPolicy policy(List<String> allowedHosts) {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        properties.setDocumentSourceAllowedHosts(allowedHosts);
        return new DocumentSourceUrlPolicy(properties);
    }
}
