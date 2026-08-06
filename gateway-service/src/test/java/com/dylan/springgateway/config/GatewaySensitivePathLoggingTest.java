package com.dylan.springgateway.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.web.server.ServerWebExchange;

@ExtendWith(OutputCaptureExtension.class)
class GatewaySensitivePathLoggingTest {
    private static final String SENTINEL = "SYNTHETIC-GATEWAY-EMPLOYEE-SENTINEL";
    private static final String TOKEN = "synthetic-gateway-token";

    @Test
    void authFilterForwardsAuthenticationWithoutLoggingTheRequestPath(CapturedOutput output) {
        JwtDecoder jwtDecoder = token -> Jwt.withTokenValue(token)
                .header("alg", "HS256")
                .subject("synthetic-gateway-user")
                .issuedAt(Instant.parse("2026-08-06T00:00:00Z"))
                .expiresAt(Instant.parse("2026-08-06T01:00:00Z"))
                .claims(claims -> claims.putAll(Map.of("token_type", "user", "role", "ADMIN")))
                .build();
        GlobalFilter filter = new GatewaySecurityConfig().authTokenFilter(jwtDecoder);
        String path = "/employees/" + SENTINEL;
        MockServerWebExchange exchange = MockServerWebExchange.from(MockServerHttpRequest.get(path)
                .header(HttpHeaders.AUTHORIZATION, "Bearer " + TOKEN)
                .build());
        AtomicReference<ServerWebExchange> forwarded = new AtomicReference<>();

        filter.filter(exchange, candidate -> {
            forwarded.set(candidate);
            return candidate.getResponse().setComplete();
        }).block();

        assertThat(forwarded.get()).isNotNull();
        assertThat(forwarded.get().getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION))
                .isEqualTo("Bearer " + TOKEN);
        assertThat(forwarded.get().getRequest().getHeaders().getFirst("X-USER-ID"))
                .isEqualTo("synthetic-gateway-user");
        assertThat(output.getAll())
                .doesNotContain(path)
                .doesNotContain(SENTINEL)
                .doesNotContain(TOKEN);
    }
}
