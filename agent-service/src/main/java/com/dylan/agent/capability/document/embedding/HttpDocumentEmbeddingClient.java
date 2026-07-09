package com.dylan.agent.capability.document.embedding;

import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** HTTP embedding provider 客户端，不记录 queryVector 原值。 */
public final class HttpDocumentEmbeddingClient implements DocumentEmbeddingPort {
    private final RestClient restClient;
    private final DocumentProviderAuthHeaderProvider authHeaderProvider;

    public HttpDocumentEmbeddingClient(
            RestClient restClient,
            DocumentProviderAuthHeaderProvider authHeaderProvider) {
        this.restClient = Objects.requireNonNull(restClient, "restClient must not be null");
        this.authHeaderProvider = Objects.requireNonNull(authHeaderProvider, "authHeaderProvider must not be null");
    }

    @Override
    public DocumentEmbeddingResult embed(DocumentEmbeddingRequest request) {
        try {
            requireActiveDeadline(request.deadline());
            @SuppressWarnings("unchecked")
            Map<String, Object> response = restClient.post()
                    .uri("/embeddings")
                    .header(HttpHeaders.AUTHORIZATION, authHeaderProvider.authorizationHeader())
                    .header("X-Agent-Request-Id", safeHeader(request.requestId()))
                    .header("X-Agent-Deadline", request.deadline().toString())
                    .body(Map.of(
                            "requestId", safeValue(request.requestId()),
                            "input", safeValue(request.queryText()),
                            "queryVariants", safeVariants(request),
                            "domain", safeValue(request.domain()),
                            "provider", safeValue(request.provider()),
                            "model", safeValue(request.model()),
                            "expectedModel", safeValue(request.expectedModel()),
                            "expectedDimension", request.expectedDimension(),
                            "deadline", request.deadline().toString()))
                    .retrieve()
                    .body(Map.class);
            requireActiveDeadline(request.deadline());
            return toResult(response, request);
        } catch (RestClientResponseException ex) {
            if (supportsEmbedFallback(ex)) {
                return embedViaTextEndpoint(request);
            }
            throw providerCallFailed();
        } catch (RestClientException | ClassCastException | IllegalArgumentException ex) {
            throw providerCallFailed();
        }
    }

    private DocumentEmbeddingResult embedViaTextEndpoint(DocumentEmbeddingRequest request) {
        try {
            requireActiveDeadline(request.deadline());
            @SuppressWarnings("unchecked")
            Map<String, Object> response = restClient.post()
                    .uri("/embed")
                    .header(HttpHeaders.AUTHORIZATION, authHeaderProvider.authorizationHeader())
                    .header("X-Agent-Request-Id", safeHeader(request.requestId()))
                    .header("X-Agent-Deadline", request.deadline().toString())
                    .body(Map.of("texts", safeVariants(request)))
                    .retrieve()
                    .body(Map.class);
            requireActiveDeadline(request.deadline());
            return toEmbedEndpointResult(response, request);
        } catch (RestClientException | ClassCastException | IllegalArgumentException ex) {
            throw providerCallFailed();
        }
    }

    private static boolean supportsEmbedFallback(RestClientResponseException ex) {
        int status = ex.getStatusCode().value();
        return status == 404 || status == 405;
    }

    private static IllegalStateException providerCallFailed() {
        return new IllegalStateException("document embedding provider call failed");
    }

    private DocumentEmbeddingResult toResult(Map<String, Object> response, DocumentEmbeddingRequest request) {
        if (response == null || !(response.get("queryVector") instanceof List<?> vector) || vector.isEmpty()) {
            throw new IllegalArgumentException("embedding provider returned invalid vector");
        }
        if (!(response.get("dimension") instanceof Number dimension)) {
            throw new IllegalArgumentException("embedding provider returned invalid dimension");
        }
        List<Double> values = vector.stream()
                .map(HttpDocumentEmbeddingClient::finiteDouble)
                .toList();
        String model = String.valueOf(response.getOrDefault(
                "embeddingModel",
                response.getOrDefault("modelVersion", request.model())));
        if (request.expectedDimension() > 0
                && (dimension.intValue() != request.expectedDimension()
                || values.size() != request.expectedDimension())) {
            throw new IllegalArgumentException("embedding provider returned dimension mismatch");
        }
        if (request.expectedModel() != null
                && !request.expectedModel().isBlank()
                && !request.expectedModel().equals(model)) {
            throw new IllegalArgumentException("embedding provider returned model mismatch");
        }
        return new DocumentEmbeddingResult(
                values,
                model,
                dimension.intValue(),
                String.valueOf(response.getOrDefault("digest", "")));
    }

    private DocumentEmbeddingResult toEmbedEndpointResult(Map<String, Object> response, DocumentEmbeddingRequest request) {
        if (response == null || !(response.get("vectors") instanceof List<?> vectors) || vectors.isEmpty()) {
            throw new IllegalArgumentException("embedding provider returned invalid vectors");
        }
        if (!(response.get("dim") instanceof Number dimension)) {
            throw new IllegalArgumentException("embedding provider returned invalid dimension");
        }
        int dim = dimension.intValue();
        List<List<Double>> values = new ArrayList<>();
        for (Object item : vectors) {
            if (!(item instanceof List<?> vector)) {
                throw new IllegalArgumentException("embedding provider returned invalid vector");
            }
            List<Double> numbers = vector.stream()
                    .map(HttpDocumentEmbeddingClient::finiteDouble)
                    .toList();
            if (numbers.size() != dim) {
                throw new IllegalArgumentException("embedding provider returned dimension mismatch");
            }
            values.add(numbers);
        }
        if (request.expectedDimension() > 0 && dim != request.expectedDimension()) {
            throw new IllegalArgumentException("embedding provider returned dimension mismatch");
        }
        String model = request.model();
        if (request.expectedModel() != null
                && !request.expectedModel().isBlank()
                && !request.expectedModel().equals(model)) {
            throw new IllegalArgumentException("embedding provider returned model mismatch");
        }
        return new DocumentEmbeddingResult(
                average(values, dim),
                model,
                dim,
                String.valueOf(response.getOrDefault("digest", "")));
    }

    private static List<Double> average(List<List<Double>> vectors, int dimension) {
        double[] sum = new double[dimension];
        for (List<Double> vector : vectors) {
            for (int i = 0; i < dimension; i++) {
                sum[i] += vector.get(i);
            }
        }
        List<Double> result = new ArrayList<>(dimension);
        for (double value : sum) {
            result.add(value / vectors.size());
        }
        return result;
    }

    private static double finiteDouble(Object value) {
        if (!(value instanceof Number number)) {
            throw new IllegalArgumentException("embedding provider returned non numeric vector");
        }
        double result = number.doubleValue();
        if (!Double.isFinite(result)) {
            throw new IllegalArgumentException("embedding provider returned non finite vector");
        }
        return result;
    }

    private static void requireActiveDeadline(Instant deadline) {
        if (deadline == null || !deadline.isAfter(Instant.now())) {
            throw new IllegalArgumentException("document embedding provider deadline expired");
        }
    }

    private static String safeValue(String value) {
        return value == null ? "" : value;
    }

    private static String safeHeader(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }

    private static List<String> safeVariants(DocumentEmbeddingRequest request) {
        List<String> variants = request.queryVariants();
        if (variants == null || variants.isEmpty()) {
            return request.queryText() == null ? List.of() : List.of(request.queryText());
        }
        return variants.stream()
                .filter(value -> value != null && !value.isBlank())
                .map(String::trim)
                .distinct()
                .toList();
    }
}
