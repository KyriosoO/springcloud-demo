package com.dylan.esquery.service;

import com.dylan.esquery.api.model.VectorSearchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class EsDocumentServiceTest {
    private EsDocumentService service;

    @BeforeEach
    void setUp() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10_000);
        properties.setRebuildSourceAllowedHosts(List.of("employee-service"));
        properties.afterPropertiesSet();
        service = new EsDocumentService(null, new ObjectMapper(), properties);
    }

    @Test
    void addsDefaultTrackTotalHitsWithoutOverridingCallerValue() {
        assertThat(service.applyDefaultTrackTotalHits("{\"query\":{\"match_all\":{}}}"))
                .contains("\"track_total_hits\":10000");
        assertThat(service.applyDefaultTrackTotalHits("{\"track_total_hits\":7}"))
                .contains("\"track_total_hits\":7");
    }

    @Test
    void buildsBoundedGenericVectorSearchBody() {
        VectorSearchRequest request = new VectorSearchRequest();
        request.setEmbeddingField("embedding_v2");request.setQueryVector(List.of(0.1, 0.2));
        request.setK(5);request.setNumCandidates(20);request.setFilter(Map.of("term", Map.of("tenantId", "t1")));
        Map<String,Object> body = service.vectorSearchBody(request);
        assertThat(body).containsKey("knn");
        assertThat(body.toString()).contains("embedding_v2", "tenantId");
    }

    @Test
    void rejectsInvalidGenericSearchBounds() {
        VectorSearchRequest request = new VectorSearchRequest();request.setQueryVector(List.of(0.1));request.setK(0);
        assertThatThrownBy(() -> service.vectorSearchBody(request))
                .isInstanceOf(IllegalArgumentException.class).hasMessageContaining("k must be positive");
    }
}
