package com.dylan.common.security;

import java.text.ParseException;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Set;

import javax.crypto.SecretKey;

import com.nimbusds.jwt.SignedJWT;
import com.nimbusds.jose.JOSEObjectType;
import com.nimbusds.jose.proc.DefaultJOSEObjectTypeVerifier;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;

public final class KidAwareJwtDecoder implements JwtDecoder {

	private final JwtKeyProvider jwtKeyProvider;
	private final Map<String, NimbusJwtDecoder> decoders = new ConcurrentHashMap<>();
	private volatile OAuth2TokenValidator<Jwt> jwtValidator;
	private volatile Set<JOSEObjectType> allowedTypes = Set.of();

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
		return decoders.computeIfAbsent(keyId, ignored -> createDecoder(key)).decode(token);
	}

	public void setJwtValidator(OAuth2TokenValidator<Jwt> jwtValidator) {
		this.jwtValidator = Objects.requireNonNull(jwtValidator, "jwtValidator must not be null");
		decoders.values().forEach(decoder -> decoder.setJwtValidator(jwtValidator));
	}

	public void setAllowedTypes(Set<String> allowedTypes) {
		this.allowedTypes = allowedTypes.stream().map(JOSEObjectType::new).collect(java.util.stream.Collectors.toSet());
		decoders.clear();
	}

	private static String keyId(String token) {
		try {
			return SignedJWT.parse(token).getHeader().getKeyID();
		} catch (ParseException ex) {
			throw new JwtException("Invalid JWT format", ex);
		}
	}

	private NimbusJwtDecoder createDecoder(SecretKey key) {
		var builder = NimbusJwtDecoder.withSecretKey(key);
		Set<JOSEObjectType> types = allowedTypes;
		if (!types.isEmpty()) {
			builder.jwtProcessorCustomizer(processor ->
					processor.setJWSTypeVerifier(new DefaultJOSEObjectTypeVerifier<>(types)));
		}
		NimbusJwtDecoder decoder = builder.build();
		OAuth2TokenValidator<Jwt> validator = jwtValidator;
		if (validator != null) {
			decoder.setJwtValidator(validator);
		}
		return decoder;
	}
}
