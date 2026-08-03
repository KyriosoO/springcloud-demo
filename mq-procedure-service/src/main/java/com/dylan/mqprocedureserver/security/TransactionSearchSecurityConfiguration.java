package com.dylan.mqprocedureserver.security;

import reactor.core.publisher.Mono;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.core.convert.converter.Converter;
import org.springframework.http.HttpMethod;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.security.web.server.util.matcher.ServerWebExchangeMatcher;
import org.springframework.security.web.server.util.matcher.ServerWebExchangeMatchers;

@Configuration(proxyBeanMethods = false)
public class TransactionSearchSecurityConfiguration {

	@Bean
	@Order(1)
	SecurityWebFilterChain transactionSearchSecurityWebFilterChain(ServerHttpSecurity http,
			@Qualifier("reactiveUserRoleJwtAuthenticationConverter")
			Converter<Jwt, Mono<AbstractAuthenticationToken>> converter) {
		return http.securityMatcher(transactionSearchMatcher())
				.csrf(ServerHttpSecurity.CsrfSpec::disable)
				.authorizeExchange(auth -> auth.anyExchange()
						.hasAnyAuthority("ROLE_ADMIN", "ROLE_VIEWER"))
				.oauth2ResourceServer(oauth2 -> oauth2
						.jwt(jwt -> jwt.jwtAuthenticationConverter(converter)))
				.build();
	}

	@Bean
	@Order(2)
	SecurityWebFilterChain transactionFallbackSecurityWebFilterChain(ServerHttpSecurity http) {
		return http.csrf(ServerHttpSecurity.CsrfSpec::disable)
				.authorizeExchange(auth -> auth
						.pathMatchers("/ws/**").permitAll()
						.anyExchange().authenticated())
				.oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
				.build();
	}

	static ServerWebExchangeMatcher transactionSearchMatcher() {
		return ServerWebExchangeMatchers.pathMatchers(HttpMethod.POST, "/txn/search");
	}
}
