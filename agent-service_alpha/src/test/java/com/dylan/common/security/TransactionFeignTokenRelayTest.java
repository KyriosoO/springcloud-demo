package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.Map;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import feign.RequestInterceptor;
import feign.RequestTemplate;

class TransactionFeignTokenRelayTest {

    @AfterEach
    void clearContext() {
        SecurityContextHolder.clearContext();
    }

    @SuppressWarnings("unchecked")
    @Test
    void shouldRelayCurrentUserJwtWithoutEmptyAuthorization() {
        Jwt jwt = new Jwt(
                "transaction-user-token",
                Instant.parse("2026-06-23T10:00:00Z"),
                Instant.parse("2026-06-23T11:00:00Z"),
                Map.of("alg", "HS256"),
                Map.of("sub", "viewer", "role", java.util.List.of("agent:viewer")));
        SecurityContextHolder.getContext().setAuthentication(new JwtAuthenticationToken(jwt));
        ObjectProvider<ServiceTokenProvider> provider = mock(ObjectProvider.class);
        when(provider.getIfAvailable()).thenReturn(null);
        RequestInterceptor interceptor =
                new FeignTokenRelayAutoConfiguration().feignTokenRelayInterceptor(provider);
        RequestTemplate template = new RequestTemplate();

        interceptor.apply(template);

        assertThat(template.headers().get(HttpHeaders.AUTHORIZATION))
                .containsExactly("Bearer transaction-user-token")
                .doesNotContain("");
    }
}
