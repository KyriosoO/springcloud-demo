package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentRetrievalMapperTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DocumentRetrievalMapper mapper = new DocumentRetrievalMapper(objectMapper);

    @Test
    void mapsContainsAnyToShouldMatchClauses() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("sourceType", AgentOperator.CONTAINS_ANY, null, List.of("policy", "guide")))));

        JsonNode filter = root.path("query").path("bool").path("must").get(1);
        assertThat(filter.path("bool").path("minimum_should_match").asInt()).isEqualTo(1);
        assertThat(filter.path("bool").path("should").get(0).path("match").path("sourceType").asText())
                .isEqualTo("policy");
        assertThat(filter.path("bool").path("should").get(1).path("match").path("sourceType").asText())
                .isEqualTo("guide");
    }

    @Test
    void mapsStartsWithAnyToShouldPrefixClauses() throws Exception {
        JsonNode root = objectMapper.readTree(mapper.toSearchDsl(request(
                new ValidatedFilter("title", AgentOperator.STARTS_WITH_ANY, null, List.of("制度", "规范")))));

        JsonNode filter = root.path("query").path("bool").path("must").get(1);
        assertThat(filter.path("bool").path("minimum_should_match").asInt()).isEqualTo(1);
        assertThat(filter.path("bool").path("should").get(0).path("prefix").path("title").asText())
                .isEqualTo("制度");
        assertThat(filter.path("bool").path("should").get(1).path("prefix").path("title").asText())
                .isEqualTo("规范");
    }

    private DocumentRetrievalRequest request(ValidatedFilter filter) {
        return new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                "policy_document",
                "休假政策",
                List.of(filter),
                List.of(),
                5,
                1,
                5,
                null,
                false);
    }
}
