package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.document.DocumentContextOptions;
import com.dylan.agent.adapter.api.document.DocumentHybridOptions;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.esquery.api.model.HybridContextWindow;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class DocumentRetrievalMapper {

    private final ObjectMapper objectMapper;
    private final DocumentAclFilterFactory aclFilterFactory;

    public DocumentRetrievalMapper(ObjectMapper objectMapper) {
        this(objectMapper, new DocumentAclFilterFactory());
    }

    public DocumentRetrievalMapper(ObjectMapper objectMapper, DocumentAclFilterFactory aclFilterFactory) {
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
        this.aclFilterFactory = Objects.requireNonNull(aclFilterFactory, "aclFilterFactory must not be null");
    }

    public String toSearchDsl(DocumentRetrievalRequest request) {
        Map<String, Object> root = searchDsl(request, true);
        try {
            return objectMapper.writeValueAsString(root);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to build document search DSL", ex);
        }
    }

    private Map<String, Object> searchDsl(DocumentRetrievalRequest request, boolean includeFilters) {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("from", Math.max(0, (request.getPage() - 1) * request.getSize()));
        root.put("size", request.getSize());
        root.put("query", query(request, includeFilters));
        if (!request.getSorts().isEmpty()) {
            root.put("sort", request.getSorts().stream()
                    .map(this::sort)
                    .toList());
        }
        return root;
    }

    public HybridSearchRequest toHybridRequest(DocumentRetrievalRequest request) {
        HybridSearchRequest hybrid = new HybridSearchRequest();
        hybrid.setQueryText(request.getQueryText());
        hybrid.setKeywordDsl(toKeywordDslMap(request));
        hybrid.setFilters(filterDsl(request));
        hybrid.setQueryVector(request.getQueryVector());
        hybrid.setTopK(request.getTopK());
        DocumentHybridOptions options = request.getHybridOptions();
        if (options != null) {
            hybrid.setKeywordK(options.keywordK());
            hybrid.setVectorK(options.vectorK());
            hybrid.setRrfK(options.rrfK());
            hybrid.setNumCandidates(options.numCandidates());
        }
        hybrid.setContextWindow(toContextWindow(request.getContextOptions()));
        return hybrid;
    }

    public VectorSearchRequest toVectorRequest(DocumentRetrievalRequest request) {
        VectorSearchRequest vector = new VectorSearchRequest();
        vector.setQueryVector(request.getQueryVector());
        vector.setFilterDsl(filterDsl(request));
        vector.setK(request.getTopK());
        DocumentHybridOptions options = request.getHybridOptions();
        if (options != null) {
            vector.setNumCandidates(options.numCandidates());
        }
        return vector;
    }

    private Map<String, Object> toKeywordDslMap(DocumentRetrievalRequest request) {
        return searchDsl(request, false);
    }

    private HybridContextWindow toContextWindow(DocumentContextOptions options) {
        if (options == null) {
            return null;
        }
        HybridContextWindow window = new HybridContextWindow();
        window.setBeforeChunks(options.beforeChunks());
        window.setAfterChunks(options.afterChunks());
        window.setMaxContextChars(options.maxContextChars());
        return window;
    }

    private Map<String, Object> query(DocumentRetrievalRequest request, boolean includeFilters) {
        List<Object> must = new ArrayList<>();
        if (request.getQueryText() != null && !request.getQueryText().isBlank()) {
            must.add(Map.of("multi_match", Map.of(
                    "query", request.getQueryText(),
                    "fields", List.of("title^2", "content", "snippet", "section"))));
        }
        Map<String, Object> bool = new LinkedHashMap<>();
        bool.put("must", must.isEmpty() ? List.of(Map.of("match_all", Map.of())) : must);
        if (includeFilters) {
            Map<String, Object> filterDsl = filterDsl(request);
            @SuppressWarnings("unchecked")
            Map<String, Object> filterBool = (Map<String, Object>) filterDsl.get("bool");
            bool.put("filter", filterBool.get("filter"));
        }
        return Map.of("bool", bool);
    }

    private Map<String, Object> filterDsl(DocumentRetrievalRequest request) {
        List<Object> filters = request.getFilters().stream()
                .map(this::filter)
                .map(item -> (Object) item)
                .toList();
        Map<String, Object> businessFilter = filters.isEmpty() ? null : Map.of("bool", Map.of("filter", filters));
        Map<String, Object> aclFilter = aclFilterFactory.build(request.getDomain(), request.getAclScope());
        return aclFilterFactory.merge(businessFilter, aclFilter);
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
