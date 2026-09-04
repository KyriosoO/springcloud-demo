package com.dylan.agent.service.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import com.dylan.agent.service.contract.RuntimeInspectResponse;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.runtime.AgentRuntimeInspectionClient;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.web.reactive.server.WebTestClient;

import reactor.core.publisher.Mono;

@SpringBootTest(
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
                "spring.cloud.config.enabled=false",
                "spring.autoconfigure.exclude=com.dylan.common.security.JwtConfig,com.dylan.common.security.ReactiveResourceServerSecurityAutoConfiguration"
        })
@Import(AgentInspectionDisabledContractTest.Config.class)
class AgentInspectionDisabledContractTest {
    @Autowired
    private WebTestClient client;

    @Autowired
    private DisabledInspectionClient runtime;

    @Test
    void inspectionIsDisabledByDefaultWithoutCallingRuntime() {
        client.post().uri("/api/v1/agent/query-runs")
                .header("Authorization", "Bearer admin")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"上海员工\"}")
                .exchange()
                .expectStatus().isForbidden()
                .expectBody().jsonPath("$.error.code").isEqualTo("core.agent_inspection_disabled");

        assertThat(runtime.calls).hasValue(0);
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class Config {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            return token -> Mono.just(Jwt.withTokenValue(token)
                    .header("alg", "none")
                    .subject("admin")
                    .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                    .claim("role", List.of("ADMIN"))
                    .issuedAt(Instant.now())
                    .expiresAt(Instant.now().plusSeconds(60))
                    .build());
        }

        @Bean
        @Primary
        DisabledInspectionClient disabledInspectionClient() {
            return new DisabledInspectionClient();
        }
    }

    static final class DisabledInspectionClient implements AgentRuntimeInspectionClient {
        private final AtomicInteger calls = new AtomicInteger();

        @Override
        public Mono<RuntimeInspectResponse> inspect(RuntimeInvokeRequest request, String rawUserToken) {
            calls.incrementAndGet();
            return Mono.error(new AssertionError("runtime must not be called"));
        }
    }
}
