package com.dylan.agent.capability.document.generation;

import org.springframework.web.client.RestClient;

/** HTTP LLM provider 客户端。 */
public final class HttpDocumentGenerationClient implements DocumentGenerationPort {
    private final RestClient restClient;

    public HttpDocumentGenerationClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @Override
    public DocumentGenerationResult generate(DocumentGenerationRequest request) {
        DocumentGenerationResult result = restClient.post()
                .uri("/document-generation")
                .body(request)
                .retrieve()
                .body(DocumentGenerationResult.class);
        if (result == null) {
            throw new IllegalStateException("document generation provider returned empty result");
        }
        return result;
    }
}
