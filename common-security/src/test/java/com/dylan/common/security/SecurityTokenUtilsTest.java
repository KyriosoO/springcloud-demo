package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

class SecurityTokenUtilsTest {

    @Test
    void authorizesOnlyExpectedServiceAndScope() {
        Jwt token = serviceToken("agent-service", "agent.employee.query other.scope");

        assertThat(SecurityTokenUtils.isServiceTokenAuthorized(
                token, "agent-service", "agent.employee.query")).isTrue();
        assertThat(SecurityTokenUtils.isServiceTokenAuthorized(
                token, "other-service", "agent.employee.query")).isFalse();
        assertThat(SecurityTokenUtils.isServiceTokenAuthorized(
                token, "agent-service", "agent.transaction.query")).isFalse();
    }

    @Test
    void acceptsUserOrExpectedScopedServiceForUnifiedBusinessEndpoint() {
        Jwt userToken = token("dylan", SecurityTokenUtils.USER_TOKEN_TYPE, null);
        Jwt serviceToken = serviceToken("agent-service", "agent.employee.query");
        Jwt otherServiceToken = serviceToken("other-service", "agent.employee.query");

        assertThat(SecurityTokenUtils.isUserOrAuthorizedService(
                userToken, "agent-service", "agent.employee.query")).isTrue();
        assertThat(SecurityTokenUtils.isUserOrAuthorizedService(
                serviceToken, "agent-service", "agent.employee.query")).isTrue();
        assertThat(SecurityTokenUtils.isUserOrAuthorizedService(
                otherServiceToken, "agent-service", "agent.employee.query")).isFalse();
    }

    private static Jwt serviceToken(String subject, String scopes) {
        return token(subject, SecurityTokenUtils.SERVICE_TOKEN_TYPE, scopes);
    }

    private static Jwt token(String subject, String tokenType, String scopes) {
        Instant now = Instant.parse("2026-07-16T00:00:00Z");
        Jwt.Builder builder = Jwt.withTokenValue("token")
                .header("alg", "none")
                .subject(subject)
                .issuedAt(now)
                .expiresAt(now.plusSeconds(300))
                .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType);
        if (scopes != null) {
            builder.claim("scope", scopes);
        }
        return builder.build();
    }
}
