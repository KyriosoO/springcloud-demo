package com.dylan.agent.capability.document.rerank;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** HTTP rerank provider 客户端，输入只使用已安全投影的候选字段。 */
public final class HttpDocumentRerankClient implements DocumentRerankPort {
    private static final String DEFAULT_PATH = "/rerank";
    private static final int DEFAULT_MAX_DOCUMENT_CHARS = 1200;

    private final RestClient restClient;
    private final DocumentProviderAuthHeaderProvider authHeaderProvider;
    private final String path;
    private final String model;
    private final boolean normalize;
    private final int maxDocumentChars;

    public HttpDocumentRerankClient(
            RestClient restClient,
            DocumentProviderAuthHeaderProvider authHeaderProvider,
            String path,
            String model,
            boolean normalize,
            int maxDocumentChars) {
        this.restClient = Objects.requireNonNull(restClient, "restClient must not be null");
        this.authHeaderProvider = Objects.requireNonNull(authHeaderProvider, "authHeaderProvider must not be null");
        this.path = path == null || path.isBlank() ? DEFAULT_PATH : path.trim();
        this.model = model == null || model.isBlank() ? "unknown" : model.trim();
        this.normalize = normalize;
        this.maxDocumentChars = maxDocumentChars <= 0 ? DEFAULT_MAX_DOCUMENT_CHARS : maxDocumentChars;
    }

    @Override
    public AdapterDocumentResult rerank(DocumentRerankRequest request) {
        try {
            requireActiveDeadline(request.absoluteDeadline());
            List<Candidate> candidates = candidates(request);
            if (candidates.isEmpty()) {
                return new AdapterDocumentResult();
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> response = restClient.post()
                    .uri(path)
                    .header(HttpHeaders.AUTHORIZATION, authHeaderProvider.authorizationHeader())
                    .header("X-Agent-Request-Id", safeHeader(request.invocationId()))
                    .header("X-Agent-Deadline", request.absoluteDeadline().toString())
                    .body(Map.of(
                            "query", requireNonBlank(request.queryText(), "query"),
                            "documents", candidates.stream().map(Candidate::document).toList(),
                            "top_n", candidates.size(),
                            "normalize", normalize))
                    .retrieve()
                    .body(Map.class);
            requireActiveDeadline(request.absoluteDeadline());
            return toResult(response, candidates);
        } catch (RestClientException | ClassCastException | IllegalArgumentException ex) {
            throw providerCallFailed();
        }
    }

    private List<Candidate> candidates(DocumentRerankRequest request) {
        if (request == null || request.candidates() == null || request.candidates().getHits() == null) {
            return List.of();
        }
        int limit = Math.max(1, request.topN());
        List<Candidate> candidates = new ArrayList<>();
        List<AdapterDocumentEvidence> hits = request.candidates().getHits();
        for (int i = 0; i < hits.size() && candidates.size() < limit; i++) {
            AdapterDocumentEvidence evidence = hits.get(i);
            if (evidence == null) {
                continue;
            }
            String document = rerankDocument(evidence);
            if (!document.isBlank()) {
                candidates.add(new Candidate(candidates.size(), evidence, document));
            }
        }
        return List.copyOf(candidates);
    }

    private String rerankDocument(AdapterDocumentEvidence evidence) {
        List<String> parts = new ArrayList<>();
        add(parts, "标题", evidence.getTitle());
        add(parts, "章节", evidence.getSection());
        add(parts, "摘要", evidence.getSnippet());
        Map<String, Object> metadata = evidence.getMetadata();
        if (metadata != null) {
            add(parts, "文号", metadata.get("documentNo"));
            add(parts, "发文机关", metadata.get("issuer"));
            add(parts, "税种", metadata.get("taxType"));
            add(parts, "效力", metadata.get("validityStatus"));
            add(parts, "发布日期", metadata.get("effectiveDate"));
        }
        String document = String.join("\n", parts).trim();
        return document.length() <= maxDocumentChars ? document : document.substring(0, maxDocumentChars);
    }

    private AdapterDocumentResult toResult(Map<String, Object> response, List<Candidate> candidates) {
        if (response == null || !(response.get("results") instanceof List<?> results)) {
            throw new IllegalArgumentException("rerank provider returned invalid results");
        }
        Map<Integer, Candidate> candidateByIndex = new LinkedHashMap<>();
        candidates.forEach(candidate -> candidateByIndex.put(candidate.index(), candidate));
        List<AdapterDocumentEvidence> hits = new ArrayList<>();
        for (Object result : results) {
            if (!(result instanceof Map<?, ?> item)) {
                continue;
            }
            Object indexValue = item.get("index");
            Object scoreValue = item.get("score");
            if (!(indexValue instanceof Number indexNumber) || !(scoreValue instanceof Number scoreNumber)) {
                continue;
            }
            Candidate candidate = candidateByIndex.remove(indexNumber.intValue());
            if (candidate == null) {
                continue;
            }
            AdapterDocumentEvidence evidence = candidate.evidence();
            evidence.setScore(BigDecimal.valueOf(scoreNumber.doubleValue()));
            Map<String, Object> metadata = new LinkedHashMap<>(
                    evidence.getMetadata() == null ? Map.of() : evidence.getMetadata());
            metadata.put("rerankScore", scoreNumber.doubleValue());
            metadata.put("rerankReasonCode", model);
            evidence.setMetadata(metadata);
            hits.add(evidence);
        }
        if (hits.isEmpty()) {
            throw new IllegalArgumentException("rerank provider returned no usable results");
        }
        AdapterDocumentResult result = new AdapterDocumentResult();
        result.setHits(hits);
        result.setCitations(hits);
        return result;
    }

    private static void add(List<String> parts, String name, Object value) {
        if (value == null) {
            return;
        }
        String text = String.valueOf(value).trim();
        if (!text.isBlank()) {
            parts.add(name + "：" + text);
        }
    }

    private static void requireActiveDeadline(Instant deadline) {
        if (deadline == null || !deadline.isAfter(Instant.now())) {
            throw new IllegalArgumentException("document rerank provider deadline expired");
        }
    }

    private static String requireNonBlank(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }

    private static String safeHeader(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }

    private static IllegalStateException providerCallFailed() {
        return new IllegalStateException("document rerank provider call failed");
    }

    private record Candidate(int index, AdapterDocumentEvidence evidence, String document) {
    }
}
