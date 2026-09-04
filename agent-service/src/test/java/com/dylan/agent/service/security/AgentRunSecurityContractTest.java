package com.dylan.agent.service.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureResponse;
import com.dylan.agent.service.contract.FailureSource;
import com.dylan.agent.service.contract.RuntimeInspectResponse;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.runtime.AgentRuntimeInspectionClient;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.web.reactive.server.WebTestClient;

import reactor.core.publisher.Mono;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "spring.cloud.config.enabled=false",
                "agent.inspection.enabled=true",
                "spring.autoconfigure.exclude=com.dylan.common.security.JwtConfig,com.dylan.common.security.ReactiveResourceServerSecurityAutoConfiguration"
        })
@Import(AgentRunSecurityContractTest.TestAccessConfiguration.class)
class AgentRunSecurityContractTest {
    @Autowired
    private WebTestClient client;

    @Autowired
    private CapturingInspectionClient runtime;

    @BeforeEach
    void reset() {
        runtime.calls.set(0);
    }

    @Test
    void onlyAdminCanExecuteInspectionWhilePageNeedsAuthentication() {
        client.get().uri("/agent.html")
                .header("Authorization", "Bearer viewer")
                .exchange()
                .expectStatus().isOk()
                .expectBody(String.class)
                .value(body -> assertThat(body)
                        .contains(
                                "用户问题",
                                "发送给 LLM 的请求（安全结构化投影）",
                                "结构化 Plan",
                                "下游查询请求",
                                "Knowledge 证据摘要（加工后文本）",
                                "完整结构化结果",
                                "answerSummary")
                        .contains("/api/v1/agent/query-runs")
                        .doesNotContain("structuredOutput", "innerHTML", "localStorage"));

        client.post().uri("/api/v1/agent/query-runs")
                .header("Authorization", "Bearer viewer")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"上海员工\"}")
                .exchange()
                .expectStatus().isForbidden()
                .expectBody().jsonPath("$.error.code").isEqualTo("core.access_denied");

        client.post().uri("/api/v1/agent/query-runs")
                .header("Authorization", "Bearer admin")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"上海员工\"}")
                .exchange()
                .expectStatus().isEqualTo(422)
                .expectBody()
                .jsonPath("$.modelCalls").isArray()
                .jsonPath("$.plans").isArray()
                .jsonPath("$.downstreamCalls").isArray();

        assertThat(runtime.calls).hasValue(1);
    }

    @Test
    void invalidBodyFailsBeforeInspectionRuntime() {
        client.post().uri("/api/v1/agent/query-runs")
                .header("Authorization", "Bearer admin")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"q\",\"extra\":true}")
                .exchange()
                .expectStatus().isBadRequest()
                .expectBody().jsonPath("$.error.code").isEqualTo("core.invalid_request");
        assertThat(runtime.calls).hasValue(0);
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class TestAccessConfiguration {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            return token -> switch (token) {
                case "admin" -> Mono.just(jwt(token, "ADMIN"));
                case "viewer" -> Mono.just(jwt(token, "VIEWER"));
                default -> Mono.error(new JwtException("invalid"));
            };
        }

        @Bean
        @Primary
        CapturingInspectionClient capturingInspectionClient() {
            return new CapturingInspectionClient();
        }

        private static Jwt jwt(String token, String role) {
            return Jwt.withTokenValue(token)
                    .header("alg", "none")
                    .subject(role.toLowerCase())
                    .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                    .claim("role", List.of(role))
                    .issuedAt(Instant.now())
                    .expiresAt(Instant.now().plusSeconds(60))
                    .build();
        }
    }

    static final class CapturingInspectionClient implements AgentRuntimeInspectionClient {
        private final AtomicInteger calls = new AtomicInteger();

        @Override
        public Mono<RuntimeInspectResponse> inspect(RuntimeInvokeRequest request, String rawUserToken) {
            calls.incrementAndGet();
            return Mono.just(new RuntimeInspectResponse(
                    1, request.requestId(), CapabilityStatus.UNSUPPORTED, null,
                    "当前不支持该查询。", null,
                    new FailureResponse("core.no_enabled_capability", FailureSource.CORE),
                    List.of(), List.of(), List.of()));
        }
    }
}
