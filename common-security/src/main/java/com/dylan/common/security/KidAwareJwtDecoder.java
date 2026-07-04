package com.dylan.common.security;

import java.text.ParseException;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;

import javax.crypto.SecretKey;

import com.nimbusds.jwt.SignedJWT;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;

public final class KidAwareJwtDecoder implements JwtDecoder {

	private final JwtKeyProvider jwtKeyProvider;
	private final Map<String, JwtDecoder> decoders = new ConcurrentHashMap<>();

	public KidAwareJwtDecoder(JwtKeyProvider jwtKeyProvider) {
		this.jwtKeyProvider = Objects.requireNonNull(jwtKeyProvider, "jwtKeyProvider must not be null");
	}

	@Override
	public Jwt decode(String token) throws JwtException {
		String keyId = keyId(token);
		if (keyId == null || keyId.isBlank()) {
			throw new JwtException("JWT kid is required");
		}
		SecretKey key = jwtKeyProvider.current().verificationKeys().get(keyId);
		if (key == null) {
			throw new JwtException("Unknown JWT kid");
		}
		return decoders.computeIfAbsent(keyId, ignored -> NimbusJwtDecoder.withSecretKey(key).build()).decode(token);
	}

	private static String keyId(String token) {
		try {
			return SignedJWT.parse(token).getHeader().getKeyID();
		} catch (ParseException ex) {
			throw new JwtException("Invalid JWT format", ex);
		}
	}
}
