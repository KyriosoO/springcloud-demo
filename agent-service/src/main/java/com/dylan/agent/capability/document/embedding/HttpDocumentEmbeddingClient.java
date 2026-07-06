package com.dylan.agent.capability.document.embedding;

import org.springframework.web.client.RestClient;

import java.util.Map;

/** HTTP embedding provider 客户端，不记录 queryVector 原值。 */
public final class HttpDocumentEmbeddingClient implements DocumentEmbeddingPort {
    private final RestClient restClient;

    public HttpDocumentEmbeddingClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @Override
    public DocumentEmbeddingResult embed(DocumentEmbeddingRequest request) {
        @SuppressWarnings("unchecked")
        Map<String, Object> response = restClient.post()
                .uri("/embeddings")
                .body(Map.of(
                        "requestId", request.requestId(),
                        "input", request.queryText(),
                        "model", request.model() == null ? "" : request.model()))
                .retrieve()
                .body(Map.class);
        if (response == null || !(response.get("queryVector") instanceof java.util.List<?> vector)) {
            throw new IllegalStateException("embedding provider returned empty queryVector");
        }
        @SuppressWarnings("unchecked")
        java.util.List<Double> values = vector.stream()
                .map(value -> ((Number) value).doubleValue())
                .toList();
        return new DocumentEmbeddingResult(
                values,
                String.valueOf(response.getOrDefault("embeddingModel", request.model())),
                values.size(),
                String.valueOf(response.getOrDefault("digest", "")));
    }
}
