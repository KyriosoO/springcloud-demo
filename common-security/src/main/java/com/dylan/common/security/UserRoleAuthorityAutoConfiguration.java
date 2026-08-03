package com.dylan.common.security;

import reactor.core.publisher.Mono;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.ReactiveJwtAuthenticationConverterAdapter;

/** Provides the stable, opt-in user-role converters for Servlet and Reactive security chains. */
@AutoConfiguration(after = JwtConfig.class)
public class UserRoleAuthorityAutoConfiguration {

	@Bean(name = "userRoleJwtAuthenticationConverter")
	@ConditionalOnMissingBean(name = "userRoleJwtAuthenticationConverter")
	Converter<Jwt, AbstractAuthenticationToken> userRoleJwtAuthenticationConverter() {
		return new UserRoleJwtAuthenticationConverter();
	}

	@Bean(name = "reactiveUserRoleJwtAuthenticationConverter")
	@ConditionalOnMissingBean(name = "reactiveUserRoleJwtAuthenticationConverter")
	Converter<Jwt, Mono<AbstractAuthenticationToken>> reactiveUserRoleJwtAuthenticationConverter(
			@Qualifier("userRoleJwtAuthenticationConverter")
			Converter<Jwt, AbstractAuthenticationToken> delegate) {
		return new ReactiveJwtAuthenticationConverterAdapter(delegate);
	}
}
