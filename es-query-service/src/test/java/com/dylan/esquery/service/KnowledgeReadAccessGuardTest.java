package com.dylan.esquery.service;

import static com.dylan.esquery.KnowledgeTestProfiles.enabledProperties;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeAuthorityUnavailableException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeForbiddenException;

class KnowledgeReadAccessGuardTest {

	private final KnowledgeReadAccessGuard guard = new KnowledgeReadAccessGuard(
			enabledProperties("0".repeat(64)));

	@Test
	void allowsOnlyFiniteUserAuthorities() {
		KnowledgeReadDecision decision = guard.authorize(authentication("user", "ROLE_ADMIN"),
				"tax.policy", "tax-policy-v1");
		assertThat(decision.readPolicyVersion()).isEqualTo("tax-public-authenticated-v1");

		assertThatThrownBy(() -> guard.authorize(authentication("user", "ROLE_OTHER"),
				"tax.policy", "tax-policy-v1"))
				.isInstanceOf(KnowledgeForbiddenException.class);
		assertThatThrownBy(() -> guard.authorize(authentication("service", "ROLE_ADMIN"),
				"tax.policy", "tax-policy-v1"))
				.isInstanceOf(KnowledgeForbiddenException.class);
	}

	@Test
	void rejectsMixedKnownAndUnknownAuthorities() {
		JwtAuthenticationToken authentication = new JwtAuthenticationToken(jwt("user"), List.of(
				new SimpleGrantedAuthority("ROLE_ADMIN"), new SimpleGrantedAuthority("ROLE_OTHER")));
		assertThatThrownBy(() -> guard.authorize(authentication, "tax.policy", "tax-policy-v1"))
				.isInstanceOf(KnowledgeForbiddenException.class);
	}

	@Test
	void missingConfiguredProfileIsAuthorityUnavailable() {
		assertThatThrownBy(() -> guard.authorize(authentication("user", "ROLE_ADMIN"),
				"tax.law", "tax-law-v1"))
				.isInstanceOf(KnowledgeAuthorityUnavailableException.class);
	}

	private static JwtAuthenticationToken authentication(String tokenType, String authority) {
		return new JwtAuthenticationToken(jwt(tokenType), List.of(new SimpleGrantedAuthority(authority)));
	}

	private static Jwt jwt(String tokenType) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue("token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType).build();
	}
}
