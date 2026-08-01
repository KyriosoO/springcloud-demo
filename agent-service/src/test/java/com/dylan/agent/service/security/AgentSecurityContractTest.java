package com.dylan.agent.service.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;

import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureResponse;
import com.dylan.agent.service.contract.FailureSource;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.contract.RuntimeInvokeResponse;
import com.dylan.agent.service.runtime.AgentRuntimeClient;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.core.io.buffer.DefaultDataBufferFactory;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.web.reactive.server.WebTestClient;

import reactor.core.publisher.Mono;
import reactor.core.publisher.Flux;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "spring.cloud.config.enabled=false",
                "spring.autoconfigure.exclude=com.dylan.common.security.JwtConfig,com.dylan.common.security.ReactiveResourceServerSecurityAutoConfiguration"
        })
@Import(AgentSecurityContractTest.TestAccessConfiguration.class)
class AgentSecurityContractTest {
    @Autowired
    private WebTestClient client;

    @Autowired
    private CapturingRuntimeClient runtime;

    @BeforeEach
    void reset() {
        runtime.calls.set(0);
    }

    @Test
    void missingInvalidAndServiceTokensUseSafe401EnvelopeWithoutRuntime() {
        assertUnauthorized(null);
        assertUnauthorized("bad-token");
        assertUnauthorized("service-token");
        assertUnauthorized("empty-sub");
        assertUnauthorized("x".repeat(16_385));

        assertThat(runtime.calls).hasValue(0);
    }

    @Test
    void maximumSizedUserTokenReachesRuntimeWithinCombinedHeaderLimit() {
        client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer " + "x".repeat(16_384))
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"q\"}")
                .exchange()
                .expectStatus().isEqualTo(422)
                .expectBody().jsonPath("$.error.code").isEqualTo("core.no_enabled_capability");

        assertThat(runtime.calls).hasValue(1);
    }

    @Test
    void validUserInvokesRuntimeOnceAndPreservesSemanticStatus() {
        client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer valid-user")
                .header("X-Correlation-Id", "corr-safe")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"  税务政策  \"}")
                .exchange()
                .expectStatus().isEqualTo(422)
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_JSON)
                .expectBody()
                .jsonPath("$.status").isEqualTo("unsupported")
                .jsonPath("$.correlationId").isEqualTo("corr-safe")
                .jsonPath("$.error.code").isEqualTo("core.no_enabled_capability");

        assertThat(runtime.calls).hasValue(1);
        assertThat(runtime.lastRequest.question()).isEqualTo("税务政策");
        assertThat(runtime.lastToken).isEqualTo("valid-user");
    }

    @Test
    void unknownFieldWrongMediaTypeAndOversizedBodyFailBeforeRuntime() {
        request("application/json", "{\"question\":\"q\",\"model\":\"forbidden\"}")
                .expectStatus().isBadRequest()
                .expectBody().jsonPath("$.error.code").isEqualTo("core.invalid_request");
        request("text/plain", "{\"question\":\"q\"}")
                .expectStatus().isEqualTo(415)
                .expectBody().jsonPath("$.error.code").isEqualTo("core.unsupported_media_type");
        request("application/json", "{\"question\":\"" + "x".repeat(33_000) + "\"}")
                .expectStatus().isEqualTo(413)
                .expectBody().jsonPath("$.error.code").isEqualTo("core.request_body_too_large");

        assertThat(runtime.calls).hasValue(0);
    }

    @Test
    void chunkedBodyAcceptsExactByteLimitAndRejectsOneAdditionalByte() {
        chunkedRequest(32_768)
                .expectStatus().isEqualTo(422)
                .expectBody().jsonPath("$.error.code").isEqualTo("core.no_enabled_capability");
        chunkedRequest(32_769)
                .expectStatus().isEqualTo(413)
                .expectBody().jsonPath("$.error.code").isEqualTo("core.request_body_too_large");

        assertThat(runtime.calls).hasValue(1);
    }

    private WebTestClient.ResponseSpec request(String contentType, String body) {
        return client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer valid-user")
                .header("Content-Type", contentType)
                .bodyValue(body)
                .exchange();
    }

    private WebTestClient.ResponseSpec chunkedRequest(int byteCount) {
        byte[] prefix = "{\"question\":\"q\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8);
        byte[] body = java.util.Arrays.copyOf(prefix, byteCount);
        java.util.Arrays.fill(body, prefix.length, body.length, (byte) ' ');
        int split = Math.min(16_000, body.length);
        return client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer valid-user")
                .contentType(MediaType.APPLICATION_JSON)
                .body(BodyInserters.fromDataBuffers(Flux.just(
                        DefaultDataBufferFactory.sharedInstance.wrap(java.util.Arrays.copyOfRange(body, 0, split)),
                        DefaultDataBufferFactory.sharedInstance.wrap(java.util.Arrays.copyOfRange(body, split, body.length)))))
                .exchange();
    }

    private void assertUnauthorized(String token) {
        WebTestClient.RequestBodySpec request = client.post().uri("/api/v1/agent/queries")
                .contentType(MediaType.APPLICATION_JSON);
        if (token != null) {
            request.header("Authorization", "Bearer " + token);
        }
        request.bodyValue("{\"question\":\"q\"}")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody()
                .jsonPath("$.status").isEqualTo("unauthenticated")
                .jsonPath("$.error.code").isEqualTo("core.user_identity_required")
                .jsonPath("$.requestId").isNotEmpty()
                .jsonPath("$.correlationId").isNotEmpty();
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class TestAccessConfiguration {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            return token -> {
                if ((token.length() == 16_384 || token.length() == 16_385)
                        && token.chars().allMatch(value -> value == 'x')) {
                    return Mono.just(jwt(token, "dylan", SecurityTokenUtils.USER_TOKEN_TYPE));
                }
                return switch (token) {
                    case "valid-user" -> Mono.just(jwt(token, "dylan", SecurityTokenUtils.USER_TOKEN_TYPE));
                    case "service-token" -> Mono.just(
                            jwt(token, "agent-service", SecurityTokenUtils.SERVICE_TOKEN_TYPE));
                    case "empty-sub" -> Mono.just(jwtWithoutSubject(token));
                    default -> Mono.error(new JwtException("invalid"));
                };
            };
        }

        @Bean
        @Primary
        CapturingRuntimeClient capturingRuntimeClient() {
            return new CapturingRuntimeClient();
        }

        private static Jwt jwt(String token, String subject, String type) {
            return Jwt.withTokenValue(token)
                    .header("alg", "none")
                    .subject(subject)
                    .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, type)
                    .issuedAt(Instant.now())
                    .expiresAt(Instant.now().plusSeconds(60))
                    .build();
        }

        private static Jwt jwtWithoutSubject(String token) {
            return Jwt.withTokenValue(token)
                    .header("alg", "none")
                    .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                    .issuedAt(Instant.now())
                    .expiresAt(Instant.now().plusSeconds(60))
                    .build();
        }
    }

    static final class CapturingRuntimeClient implements AgentRuntimeClient {
        private final AtomicInteger calls = new AtomicInteger();
        private volatile RuntimeInvokeRequest lastRequest;
        private volatile String lastToken;

        @Override
        public Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken) {
            calls.incrementAndGet();
            lastRequest = request;
            lastToken = rawUserToken;
            return Mono.just(new RuntimeInvokeResponse(
                    1, request.requestId(), CapabilityStatus.UNSUPPORTED, null,
                    "当前不支持该查询。", null,
                    new FailureResponse("core.no_enabled_capability", FailureSource.CORE)));
        }
    }
}
