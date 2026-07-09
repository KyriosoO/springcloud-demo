package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.adapter.api.document.DocumentContextOptions;
import com.dylan.agent.adapter.api.document.DocumentHybridOptions;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedSort;
import com.dylan.esquery.api.model.HybridContextWindow;
import com.dylan.esquery.api.model.HybridSearchChannelRequest;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.api.model.VectorSearchRequest;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class DocumentRetrievalMapper {

    private static final List<String> DEFAULT_SOURCE_EXCLUDES = List.of("embedding");

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
        root.put("_source", Map.of("excludes", DEFAULT_SOURCE_EXCLUDES));
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
        hybrid.setDomain(request.getDomain());
        hybrid.setMaterialType(request.getMaterialType());
        hybrid.setRetrievalProfile(request.getRetrievalProfile());
        hybrid.setProfileVersion(request.getProfileVersion());
        hybrid.setIndexAlias(request.getIndexAlias());
        hybrid.setKeywordDsl(toKeywordDslMap(request));
        Map<String, Object> filters = filterDsl(request);
        hybrid.setFilters(filters);
        hybrid.setPermissionEvidenceId(request.getPermissionEvidenceId());
        hybrid.setPermissionVersion(request.getPermissionVersion());
        hybrid.setFilterDigest(filterDigest(filters));
        hybrid.setQueryVector(request.getQueryVector());
        hybrid.setTopK(request.getTopK());
        DocumentHybridOptions options = request.getHybridOptions();
        if (options != null) {
            hybrid.setKeywordK(options.keywordK());
            hybrid.setVectorK(options.vectorK());
            hybrid.setExactK(options.exactK());
            hybrid.setPhraseK(options.phraseK());
            hybrid.setRrfK(options.rrfK());
            hybrid.setNumCandidates(options.numCandidates());
            hybrid.setMaxChunksPerDocument(options.maxChunksPerDocument());
            hybrid.setChannelWeights(options.channelWeights());
            hybrid.setEmbeddingField(options.embeddingField());
            hybrid.setChannels(channelRequests(request, options));
        }
        hybrid.setSourceExcludes(DEFAULT_SOURCE_EXCLUDES);
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
            vector.setEmbeddingField(options.embeddingField());
        }
        return vector;
    }

    private Map<String, Object> toKeywordDslMap(DocumentRetrievalRequest request) {
        return searchDsl(request, false);
    }

    private List<HybridSearchChannelRequest> channelRequests(
            DocumentRetrievalRequest request,
            DocumentHybridOptions options) {
        List<HybridSearchChannelRequest> channels = new ArrayList<>();
        for (String channel : options.channels()) {
            String normalized = channel == null ? "" : channel.trim().toUpperCase(java.util.Locale.ROOT);
            if (normalized.isBlank()) {
                continue;
            }
            HybridSearchChannelRequest item = new HybridSearchChannelRequest();
            item.setChannel(normalized);
            item.setWeight(options.channelWeights().get(normalized));
            switch (normalized) {
                case "BM25" -> {
                    item.setQueryDsl(toKeywordDslMap(request));
                    item.setK(options.keywordK());
                }
                case "EXACT" -> {
                    item.setQueryDsl(exactDsl(request));
                    item.setK(options.exactK());
                }
                case "PHRASE" -> {
                    item.setQueryDsl(phraseDsl(request));
                    item.setK(options.phraseK());
                }
                case "DENSE_VECTOR" -> {
                    item.setQueryVector(request.getQueryVector());
                    item.setEmbeddingField(options.embeddingField());
                    item.setK(options.vectorK());
                    item.setNumCandidates(options.numCandidates());
                }
                default -> throw new IllegalArgumentException("unsupported document retrieval channel: " + channel);
            }
            channels.add(item);
        }
        return List.copyOf(channels);
    }

    private Map<String, Object> exactDsl(DocumentRetrievalRequest request) {
        String queryText = request.getQueryText();
        List<Object> should = new ArrayList<>();
        if (queryText != null && !queryText.isBlank()) {
            should.add(namedTerm("title.keyword", queryText, "EXACT:title.keyword"));
            should.add(namedTerm("documentNo", queryText, "EXACT:documentNo"));
            should.add(namedTerm("issuer", queryText, "EXACT:issuer"));
            should.add(namedTerm("section.keyword", queryText, "EXACT:section.keyword"));
        }
        for (String keyword : request.getRuleKeywords()) {
            if (keyword != null && !keyword.isBlank()) {
                should.add(namedTerm("title.keyword", keyword, "EXACT:title.keyword"));
                should.add(namedTerm("documentNo", keyword, "EXACT:documentNo"));
            }
        }
        return channelDsl(should);
    }

    private Map<String, Object> phraseDsl(DocumentRetrievalRequest request) {
        String queryText = request.getQueryText();
        List<Object> should = new ArrayList<>();
        if (queryText != null && !queryText.isBlank()) {
            for (String field : List.of("title", "content", "snippet", "section")) {
                should.add(namedMatchPhrase(field, queryText, 2, "PHRASE:" + field));
            }
        }
        for (String candidate : request.getRewriteCandidates()) {
            if (candidate != null && !candidate.isBlank()) {
                should.add(namedMatchPhrase("content", candidate, 2, "PHRASE:content"));
            }
        }
        return channelDsl(should);
    }

    private Map<String, Object> channelDsl(List<Object> should) {
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("from", 0);
        root.put("_source", Map.of("excludes", DEFAULT_SOURCE_EXCLUDES));
        if (should == null || should.isEmpty()) {
            root.put("query", Map.of("match_all", Map.of()));
        } else {
            root.put("query", Map.of("bool", Map.of(
                    "should", should,
                    "minimum_should_match", 1)));
        }
        return root;
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
            Map<String, Object> multiMatch = new LinkedHashMap<>();
            multiMatch.put("query", request.getQueryText());
            multiMatch.put("fields", List.of("title^2", "content", "snippet", "section"));
            multiMatch.put("_name", "BM25:multi_match");
            must.add(Map.of("multi_match", multiMatch));
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
        Map<String, Object> aclFilter = aclFilterFactory.build(
                request.getDomain(),
                request.getMaterialType(),
                request.getRetrievalProfile(),
                request.getAclScope());
        return aclFilterFactory.merge(businessFilter, aclFilter);
    }

    private String filterDigest(Map<String, Object> filters) {
        try {
            byte[] payload = objectMapper.copy()
                    .configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true)
                    .writeValueAsBytes(filters);
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(payload);
            return "sha256:" + HexFormat.of().formatHex(digest);
        } catch (JsonProcessingException | NoSuchAlgorithmException ex) {
            throw new IllegalStateException("Failed to calculate document filter digest", ex);
        }
    }

    private Map<String, Object> filter(ValidatedFilter filter) {
        return switch (filter.getOperator()) {
            case EQ -> Map.of("term", Map.of(exactMatchField(filter.getField()), filter.getValue()));
            case IN -> Map.of("terms", Map.of(exactMatchField(filter.getField()), filter.getValues()));
            case CONTAINS_ANY -> anyOf("match", filter.getField(), filter.getValues());
            case CONTAINS -> Map.of("match", Map.of(filter.getField(), filter.getValue()));
            case STARTS_WITH_ANY -> anyOf("prefix", filter.getField(), filter.getValues());
            case STARTS_WITH -> Map.of("prefix", Map.of(filter.getField(), filter.getValue()));
            case GT -> Map.of("range", Map.of(filter.getField(), Map.of("gt", filter.getValue())));
            case LT -> Map.of("range", Map.of(filter.getField(), Map.of("lt", filter.getValue())));
        };
    }

    private static Map<String, Object> namedTerm(String field, String value, String name) {
        return Map.of("term", Map.of(field, Map.of("value", value, "_name", name)));
    }

    private static Map<String, Object> namedMatchPhrase(String field, String query, int slop, String name) {
        return Map.of("match_phrase", Map.of(field, Map.of(
                "query", query,
                "slop", slop,
                "_name", name)));
    }

    private String exactMatchField(String field) {
        return switch (field) {
            case "title", "section", "snippet", "author", "publication" -> field + ".keyword";
            default -> field;
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
