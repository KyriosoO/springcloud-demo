package com.dylan.employee.security;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.common.security.SecurityTokenUtils;

import java.time.Instant;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.server.ResponseStatusException;

class CapabilityAccessGuardTest {

    private final CapabilityAccessGuard guard = new CapabilityAccessGuard();

    @Test
    void acceptsUserAndRejectsServiceTokens() {
        assertThatCode(() -> guard.requireUser(
                authentication("dylan", SecurityTokenUtils.USER_TOKEN_TYPE, null)))
                .doesNotThrowAnyException();
        assertThatThrownBy(() -> guard.requireUser(
                authentication("batch-service", SecurityTokenUtils.SERVICE_TOKEN_TYPE,
                        "employee.query")))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("403 FORBIDDEN");
        assertThatThrownBy(() -> guard.requireUser(
                authentication("other-service", SecurityTokenUtils.SERVICE_TOKEN_TYPE, null)))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("403 FORBIDDEN");
    }

    private static JwtAuthenticationToken authentication(String subject, String tokenType, String scope) {
        Instant now = Instant.parse("2026-07-16T00:00:00Z");
        Jwt.Builder builder = Jwt.withTokenValue("token")
                .header("alg", "none")
                .subject(subject)
                .issuedAt(now)
                .expiresAt(now.plusSeconds(300))
                .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType);
        if (scope != null) {
            builder.claim("scope", scope);
        }
        return new JwtAuthenticationToken(builder.build());
    }
}
