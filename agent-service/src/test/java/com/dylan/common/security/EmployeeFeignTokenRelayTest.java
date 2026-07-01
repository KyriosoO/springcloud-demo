package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Map;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import feign.RequestInterceptor;
import feign.RequestTemplate;

@DisplayName("Employee Feign 用户 Token 透传")
class EmployeeFeignTokenRelayTest {

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    @SuppressWarnings("unchecked")
    @Test
    void shouldRelayCurrentUserJwt() {
        Jwt jwt = new Jwt(
                "user-token-value",
                Instant.parse("2026-06-18T10:00:00Z"),
                Instant.parse("2026-06-18T11:00:00Z"),
                Map.of("alg", "HS256"),
                Map.of("sub", "admin", "role", java.util.List.of("agent:admin")));
        SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(jwt));

        ObjectProvider<ServiceTokenProvider> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(null);
        RequestInterceptor interceptor =
                new FeignTokenRelayAutoConfiguration().feignTokenRelayInterceptor(provider);
        RequestTemplate template = new RequestTemplate();

        interceptor.apply(template);

        assertThat(template.headers().get(HttpHeaders.AUTHORIZATION))
                .containsExactly("Bearer user-token-value");
        assertThat(template.headers()).doesNotContainKey("Cookie");
    }
}
