package com.dylan.esquery.document;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentSearchAccessGuardTest {
    private final DocumentSearchAccessGuard guard = new DocumentSearchAccessGuard();

    @Test
    void acceptsOnlyAgentServiceTokenWithDedicatedScope() {
        assertThatCode(() -> guard.requireAuthorized(jwt(
                "agent-service", "service", "document:hybrid-search"))).doesNotThrowAnyException();

        assertThatThrownBy(() -> guard.requireAuthorized(jwt(
                "agent-service", "user", "document:hybrid-search")))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        ex -> assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
        assertThatThrownBy(() -> guard.requireAuthorized(jwt(
                "other-service", "service", "document:hybrid-search")))
                .isInstanceOf(ResponseStatusException.class);
        assertThatThrownBy(() -> guard.requireAuthorized(jwt(
                "agent-service", "service", "document:read")))
                .isInstanceOf(ResponseStatusException.class);
    }

    private static Jwt jwt(String subject, String tokenType, String scope) {
        Instant now = Instant.parse("2026-07-14T00:00:00Z");
        return Jwt.withTokenValue("token").header("alg", "none").subject(subject)
                .issuedAt(now).expiresAt(now.plusSeconds(60))
                .claim("token_type", tokenType).claim("scope", scope).build();
    }
}
