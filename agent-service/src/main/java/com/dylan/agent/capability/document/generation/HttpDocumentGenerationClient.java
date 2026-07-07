package com.dylan.agent.capability.document.generation;

import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Instant;
import java.util.Map;
import java.util.Objects;

/** HTTP LLM provider 客户端。 */
public final class HttpDocumentGenerationClient implements DocumentGenerationPort {
    private final RestClient restClient;
    private final DocumentProviderAuthHeaderProvider authHeaderProvider;

    public HttpDocumentGenerationClient(
            RestClient restClient,
            DocumentProviderAuthHeaderProvider authHeaderProvider) {
        this.restClient = Objects.requireNonNull(restClient, "restClient must not be null");
        this.authHeaderProvider = Objects.requireNonNull(authHeaderProvider, "authHeaderProvider must not be null");
    }

    @Override
    public DocumentGenerationResult generate(DocumentGenerationRequest request) {
        try {
            requireActiveDeadline(request.deadline());
            DocumentGenerationResult result = restClient.post()
                    .uri("/document-generation")
                    .header(HttpHeaders.AUTHORIZATION, authHeaderProvider.authorizationHeader())
                    .header("X-Agent-Request-Id", safeHeader(request.requestId()))
                    .header("X-Agent-Deadline", request.deadline().toString())
                    .body(Map.of(
                            "requestId", safeValue(request.requestId()),
                            "operation", request.operation(),
                            "queryText", safeValue(request.queryText()),
                            "model", safeValue(request.model()),
                            "contextPackage", request.contextPackage(),
                            "maxOutputChars", request.maxOutputChars(),
                            "deadline", request.deadline().toString()))
                    .retrieve()
                    .body(DocumentGenerationResult.class);
            requireActiveDeadline(request.deadline());
            if (result == null) {
                throw new IllegalArgumentException("document generation provider returned empty result");
            }
            return result;
        } catch (RestClientException | IllegalArgumentException ex) {
            throw new IllegalStateException("document generation provider call failed", ex);
        }
    }

    private static void requireActiveDeadline(Instant deadline) {
        if (deadline == null || !deadline.isAfter(Instant.now())) {
            throw new IllegalArgumentException("document generation provider deadline expired");
        }
    }

    private static String safeHeader(String value) {
        return value == null || value.isBlank() ? "unknown" : value;
    }

    private static String safeValue(String value) {
        return value == null ? "" : value;
    }
}
