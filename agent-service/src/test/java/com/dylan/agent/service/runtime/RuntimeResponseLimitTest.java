package com.dylan.agent.service.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.concurrent.atomic.AtomicReference;

import com.dylan.agent.service.config.AgentRuntimeProperties;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.contract.RuntimeSubject;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;

import reactor.core.publisher.Mono;
import reactor.netty.DisposableServer;
import reactor.netty.http.server.HttpServer;
import reactor.test.StepVerifier;

class RuntimeResponseLimitTest {
    private static final int LIMIT = 32768;

    @Test
    void acceptsBoundaryResponseAndRejectsOneAdditionalByteDuringAggregation() {
        AtomicReference<String> body = new AtomicReference<>(responseOfSize(LIMIT));
        DisposableServer server = HttpServer.create()
                .host("127.0.0.1")
                .port(0)
                .route(routes -> routes.post("/internal/v1/agent-runs:invoke", (request, response) -> response
                        .header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
                        .sendString(Mono.fromSupplier(body::get))))
                .bindNow(Duration.ofSeconds(5));
        try {
            WebClientAgentRuntimeClient client = new WebClientAgentRuntimeClient(
                    new AgentRuntimeProperties(
                            URI.create("http://127.0.0.1:" + server.port()), 1, Duration.ofSeconds(1), LIMIT),
                    new ObjectMapper().findAndRegisterModules()
                            .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES));
            RuntimeInvokeRequest request = new RuntimeInvokeRequest(
                    1, "req-limit", "corr-limit", "question", new RuntimeSubject("dylan", "user"),
                    System.currentTimeMillis() + 5_000, 5_000);

            StepVerifier.create(client.invoke(request, "synthetic-token"))
                    .assertNext(response -> assertThat(response.requestId()).isEqualTo("req-limit"))
                    .verifyComplete();

            body.set(responseOfSize(LIMIT + 1));
            StepVerifier.create(client.invoke(request, "synthetic-token"))
                    .expectErrorSatisfies(error -> {
                        assertThat(error).isInstanceOf(RuntimeClientException.class);
                        assertThat(((RuntimeClientException) error).code()).isEqualTo("core.runtime_invalid_response");
                    })
                    .verify();
        } finally {
            server.disposeNow(Duration.ofSeconds(5));
        }
    }

    private String responseOfSize(int size) {
        String prefix = "{\"contractVersion\":1,\"requestId\":\"req-limit\",\"status\":\"success\","
                + "\"capabilityId\":\"test.action\",\"answerText\":null,\"userResult\":{\"padding\":\"";
        String suffix = "\"},\"failure\":null}";
        int padding = size - prefix.getBytes(StandardCharsets.UTF_8).length
                - suffix.getBytes(StandardCharsets.UTF_8).length;
        if (padding < 0) {
            throw new IllegalArgumentException("agent.test-response-size");
        }
        String response = prefix + "x".repeat(padding) + suffix;
        assertThat(response.getBytes(StandardCharsets.UTF_8)).hasSize(size);
        return response;
    }
}
