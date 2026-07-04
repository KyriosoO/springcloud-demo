package com.dylan.common.security;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;

import reactor.core.publisher.Mono;

public final class KidAwareReactiveJwtDecoder implements ReactiveJwtDecoder {

	private final KidAwareJwtDecoder delegate;

	public KidAwareReactiveJwtDecoder(JwtKeyProvider jwtKeyProvider) {
		this.delegate = new KidAwareJwtDecoder(jwtKeyProvider);
	}

	@Override
	public Mono<Jwt> decode(String token) throws JwtException {
		return Mono.fromCallable(() -> delegate.decode(token));
	}
}
