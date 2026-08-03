package com.dylan.mqprocedureserver.security;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.common.security.SecurityTokenUtils;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.server.ResponseStatusException;

class CapabilityAccessGuardTest {

    private final CapabilityAccessGuard guard = new CapabilityAccessGuard();

    @Test
    void acceptsUserAndRejectsServiceToken() {
        assertThatCode(() -> guard.requireUser(
                authentication("dylan", SecurityTokenUtils.USER_TOKEN_TYPE, null)))
                .doesNotThrowAnyException();
        assertThatThrownBy(() -> guard.requireUser(
                authentication("batch-service", SecurityTokenUtils.SERVICE_TOKEN_TYPE, "transaction.query")))
                .isInstanceOf(ResponseStatusException.class)
                .hasMessageContaining("403 FORBIDDEN");
    }

	@Test
	void transactionReadRequiresAdminOrViewerAuthority() {
		assertThatCode(() -> guard.requireTransactionRead(
				authentication("dylan", SecurityTokenUtils.USER_TOKEN_TYPE, null, "ROLE_ADMIN")))
				.doesNotThrowAnyException();
		assertThatCode(() -> guard.requireTransactionRead(
				authentication("viewer_t", SecurityTokenUtils.USER_TOKEN_TYPE, null, "ROLE_VIEWER")))
				.doesNotThrowAnyException();
		assertThatThrownBy(() -> guard.requireTransactionRead(
				authentication("user", SecurityTokenUtils.USER_TOKEN_TYPE, null, "ROLE_OTHER")))
				.isInstanceOf(ResponseStatusException.class)
				.hasMessageContaining("403 FORBIDDEN");
	}

    private static JwtAuthenticationToken authentication(String subject, String tokenType, String scope) {
		return authentication(subject, tokenType, scope, null);
	}

	private static JwtAuthenticationToken authentication(String subject, String tokenType, String scope,
			String authority) {
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
		return authority == null ? new JwtAuthenticationToken(builder.build())
				: new JwtAuthenticationToken(builder.build(), List.of(new SimpleGrantedAuthority(authority)));
    }
}
