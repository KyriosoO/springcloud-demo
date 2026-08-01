package com.dylan.agent.service.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import java.time.Instant;

import com.dylan.agent.service.application.AgentPublicException;
import com.dylan.agent.service.config.AgentIngressProperties;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

class AgentUserContextFactoryTest {
    private final AgentUserContextFactory factory = new AgentUserContextFactory(
            new AgentIngressProperties(4096, 32768, 16384, 8,
                    Duration.ofSeconds(60), Duration.ofMillis(500)));

    @Test
    void revealsOnlyBoundedUserTokenForRuntimeAndKeepsToStringRedacted() {
        AgentUserContext maximum = factory.requireUser(jwt("dylan", "user", "x".repeat(16384)));

        assertThat(maximum.rawTokenForRuntime()).hasSize(16384);
        assertThat(maximum.toString()).doesNotContain("xxxx").contains("redacted");
        assertThatThrownBy(() -> factory.requireUser(jwt("dylan", "user", "x".repeat(16385))))
                .isInstanceOf(AgentPublicException.class);
        assertThatThrownBy(() -> factory.requireUser(jwt("svc", "service", "token")))
                .isInstanceOf(AgentPublicException.class);
    }

    private Jwt jwt(String subject, String type, String token) {
        return Jwt.withTokenValue(token)
                .header("alg", "none")
                .subject(subject)
                .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, type)
                .issuedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(60))
                .build();
    }
}
