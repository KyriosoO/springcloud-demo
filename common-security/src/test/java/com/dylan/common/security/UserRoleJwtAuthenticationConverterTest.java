package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.Test;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.jwt.Jwt;

class UserRoleJwtAuthenticationConverterTest {

	private final UserRoleJwtAuthenticationConverter converter = new UserRoleJwtAuthenticationConverter();

	@Test
	void mapsFiniteRolesWithStableOrderAndDeduplication() {
		assertAuthorities(List.of("ADMIN"), "ROLE_ADMIN");
		assertAuthorities(List.of("VIEWER"), "ROLE_VIEWER");
		assertAuthorities(List.of("VIEWER", "ADMIN", "VIEWER"), "ROLE_ADMIN", "ROLE_VIEWER");
	}

	@Test
	void invalidRoleClaimFailsClosedWithNoAuthorities() {
		assertAuthorities(null);
		assertAuthorities(List.of());
		assertAuthorities("ADMIN");
		assertAuthorities(Set.of("ADMIN"));
		assertAuthorities(List.of(List.of("ADMIN")));
		assertAuthorities(List.of(1));
		assertAuthorities(List.of(true));
		assertAuthorities(List.of(""));
		assertAuthorities(List.of("admin"));
		assertAuthorities(List.of("ADMIN", "UNKNOWN"));
	}

	@Test
	void nonUserTokenIsAnAuthenticationFailure() {
		assertThatThrownBy(() -> converter.convert(jwt(null, List.of("ADMIN"))))
				.isInstanceOf(OAuth2AuthenticationException.class);
		assertThatThrownBy(() -> converter.convert(jwt("service", List.of("ADMIN"))))
				.isInstanceOf(OAuth2AuthenticationException.class);
		assertThatThrownBy(() -> converter.convert(jwt("USER", List.of("ADMIN"))))
				.isInstanceOf(OAuth2AuthenticationException.class);
		assertThatThrownBy(() -> converter.convert(jwt(1, List.of("ADMIN"))))
				.isInstanceOf(OAuth2AuthenticationException.class);
		assertThatThrownBy(() -> converter.convert(jwt(true, List.of("ADMIN"))))
				.isInstanceOf(OAuth2AuthenticationException.class);
		assertThatThrownBy(() -> converter.convert(jwt(List.of("user"), List.of("ADMIN"))))
				.isInstanceOf(OAuth2AuthenticationException.class);
	}

	private void assertAuthorities(Object roles, String... expected) {
		AbstractAuthenticationToken authentication = converter.convert(jwt("user", roles));
		assertThat(authentication.getAuthorities())
				.extracting(Object::toString)
				.containsExactly(expected);
	}

	private static Jwt jwt(Object tokenType, Object roles) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		Jwt.Builder builder = Jwt.withTokenValue("token")
				.header("alg", "none")
				.subject("synthetic-user")
				.issuedAt(now)
				.expiresAt(now.plusSeconds(300));
		if (tokenType != null) {
			builder.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType);
		}
		if (roles != null) {
			builder.claim(UserRoleJwtAuthenticationConverter.ROLE_CLAIM, roles);
		}
		return builder.build();
	}
}
