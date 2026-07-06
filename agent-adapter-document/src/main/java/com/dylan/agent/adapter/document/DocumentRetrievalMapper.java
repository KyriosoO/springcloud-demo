package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class DocumentRetrievalMapper {

    private final ObjectMapper objectMapper;

    public DocumentRetrievalMapper(ObjectMapper objectMapper) {
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
    }

    public String toSearchDsl(DocumentRetrievalRequest request) {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("from", Math.max(0, (request.getPage() - 1) * request.getSize()));
        root.put("size", request.getSize());
        root.put("query", query(request));
        if (!request.getSorts().isEmpty()) {
            root.put("sort", request.getSorts().stream()
                    .map(this::sort)
                    .toList());
        }
        try {
            return objectMapper.writeValueAsString(root);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to build document search DSL", ex);
        }
    }

    private Map<String, Object> query(DocumentRetrievalRequest request) {
        List<Object> must = new ArrayList<>();
        if (request.getQueryText() != null && !request.getQueryText().isBlank()) {
            must.add(Map.of("multi_match", Map.of(
                    "query", request.getQueryText(),
                    "fields", List.of("title^2", "content", "snippet", "section"))));
        }
        for (ValidatedFilter filter : request.getFilters()) {
            must.add(filter(filter));
        }
        return Map.of("bool", Map.of("must", must.isEmpty() ? List.of(Map.of("match_all", Map.of())) : must));
    }

    private Map<String, Object> filter(ValidatedFilter filter) {
        return switch (filter.getOperator()) {
            case EQ -> Map.of("term", Map.of(filter.getField(), filter.getValue()));
            case IN -> Map.of("terms", Map.of(filter.getField(), filter.getValues()));
            case CONTAINS_ANY -> anyOf("match", filter.getField(), filter.getValues());
            case CONTAINS -> Map.of("match", Map.of(filter.getField(), filter.getValue()));
            case STARTS_WITH_ANY -> anyOf("prefix", filter.getField(), filter.getValues());
            case STARTS_WITH -> Map.of("prefix", Map.of(filter.getField(), filter.getValue()));
            case GT -> Map.of("range", Map.of(filter.getField(), Map.of("gt", filter.getValue())));
            case LT -> Map.of("range", Map.of(filter.getField(), Map.of("lt", filter.getValue())));
        };
    }

    private Map<String, Object> anyOf(String queryType, String field, List<String> values) {
        if (values == null || values.isEmpty()) {
            throw new IllegalArgumentException("document multi-value filter requires values");
        }
        return Map.of("bool", Map.of(
                "should", values.stream()
                        .map(value -> Map.of(queryType, Map.of(field, value)))
                        .toList(),
                "minimum_should_match", 1));
    }

    private Map<String, Object> sort(ValidatedSort sort) {
        return Map.of(sort.getField(), Map.of("order", sort.getDirection().toLowerCase(java.util.Locale.ROOT)));
    }
}
