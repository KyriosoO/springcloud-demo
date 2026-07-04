package com.dylan.common.security;

import java.util.Base64;
import java.util.Map;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.OctetSequenceKey;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jose.proc.SecurityContext;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

final class SecretTestSupport {

	static final String ACTIVE = "ACTIVE";
	static final String PREVIOUS = "PREVIOUS";
	static final String ACTIVE_SECRET = Base64.getEncoder().encodeToString(fill(1));
	static final String PREVIOUS_SECRET = Base64.getEncoder().encodeToString(fill(2));

	private SecretTestSupport() {
	}

	static SecretProperties jwtOnlyProperties() {
		SecretProperties properties = new SecretProperties();
		properties.setAllowConfigValues(true);
		properties.setSourceOrder(java.util.List.of(SecretSourceType.CONFIG, SecretSourceType.ENVIRONMENT));
		properties.getJwt().setActiveKeyId(ACTIVE);
		properties.getJwt().setPreviousKeyIds(java.util.List.of(PREVIOUS));
		properties.getJwt().setKeys(Map.of(
				ACTIVE, key(ACTIVE_SECRET),
				PREVIOUS, key(PREVIOUS_SECRET)));
		properties.getAgentPayload().setActiveKeyId(ACTIVE);
		properties.getAgentPayload().setKeys(Map.of(ACTIVE, key(ACTIVE_SECRET)));
		return properties;
	}

	static SecretKey hmacKey(byte value) {
		return new SecretKeySpec(fill(value), "HmacSHA256");
	}

	static JwtEncoder jwtEncoder(String keyId, SecretKey key) {
		OctetSequenceKey jwk = new OctetSequenceKey.Builder(key.getEncoded())
				.keyID(keyId)
				.algorithm(JWSAlgorithm.HS256)
				.build();
		return new NimbusJwtEncoder(new ImmutableJWKSet<SecurityContext>(new JWKSet(jwk)));
	}

	private static SecretProperties.KeyProperties key(String value) {
		SecretProperties.KeyProperties key = new SecretProperties.KeyProperties();
		key.setEnv("IGNORED");
		key.setValue(value);
		return key;
	}

	private static byte[] fill(int value) {
		byte[] bytes = new byte[32];
		java.util.Arrays.fill(bytes, (byte) value);
		return bytes;
	}
}
