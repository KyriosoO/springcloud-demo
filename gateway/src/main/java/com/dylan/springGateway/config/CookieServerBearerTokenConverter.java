package com.dylan.springGateway.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.server.resource.authentication.BearerTokenAuthenticationToken;
import org.springframework.security.web.server.authentication.ServerAuthenticationConverter;
import org.springframework.web.server.ServerWebExchange;

import reactor.core.publisher.Mono;

@Configuration
public class CookieServerBearerTokenConverter implements ServerAuthenticationConverter {

	private static final String COOKIE_NAME = "AUTH_TOKEN";

	@Override
	public Mono<Authentication> convert(ServerWebExchange exchange) {
		var cookie = exchange.getRequest().getCookies().getFirst(COOKIE_NAME);
		if (cookie != null) {
			return Mono.just(new BearerTokenAuthenticationToken(cookie.getValue()));
		}
		// 还可以兼容 Authorization Header
		String authHeader = exchange.getRequest().getHeaders().getFirst("Authorization");
		if (authHeader != null && authHeader.startsWith("Bearer ")) {
			return Mono.just(new BearerTokenAuthenticationToken(authHeader.substring(7)));
		}
		return Mono.empty();
	}
}
