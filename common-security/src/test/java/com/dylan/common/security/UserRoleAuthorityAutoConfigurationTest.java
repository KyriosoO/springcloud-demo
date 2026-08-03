package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;

import reactor.core.publisher.Mono;

import org.junit.jupiter.api.Test;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.Jwt;

class UserRoleAuthorityAutoConfigurationTest {

	private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
			.withConfiguration(AutoConfigurations.of(UserRoleAuthorityAutoConfiguration.class));

	@Test
	@SuppressWarnings("unchecked")
	void publishesStableServletAndReactiveBeanNamesWithTheSameSemantics() {
		contextRunner.run(context -> {
			assertThat(context).hasBean("userRoleJwtAuthenticationConverter");
			assertThat(context).hasBean("reactiveUserRoleJwtAuthenticationConverter");

			Converter<Jwt, AbstractAuthenticationToken> servlet =
					(Converter<Jwt, AbstractAuthenticationToken>) context
							.getBean("userRoleJwtAuthenticationConverter", Converter.class);
			Converter<Jwt, Mono<AbstractAuthenticationToken>> reactive =
					(Converter<Jwt, Mono<AbstractAuthenticationToken>>) context
							.getBean("reactiveUserRoleJwtAuthenticationConverter", Converter.class);

			Jwt jwt = userJwt();
			assertThat(servlet.convert(jwt).getAuthorities())
					.extracting(Object::toString)
					.containsExactly("ROLE_ADMIN", "ROLE_VIEWER");
			assertThat(reactive.convert(jwt).block().getAuthorities())
					.extracting(Object::toString)
					.containsExactly("ROLE_ADMIN", "ROLE_VIEWER");
		});
	}

	private static Jwt userJwt() {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue("token")
				.header("alg", "none")
				.subject("synthetic-user")
				.issuedAt(now)
				.expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
				.claim(UserRoleJwtAuthenticationConverter.ROLE_CLAIM, List.of("VIEWER", "ADMIN"))
				.build();
	}
}
