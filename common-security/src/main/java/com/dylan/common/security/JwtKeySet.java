package com.dylan.common.security;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

import javax.crypto.SecretKey;

public record JwtKeySet(String activeKeyId, SecretKey activeKey, Map<String, SecretKey> verificationKeys) {

	public JwtKeySet {
		SecretPropertiesValidator.validateKeyId(activeKeyId);
		Objects.requireNonNull(activeKey, "activeKey must not be null");
		Objects.requireNonNull(verificationKeys, "verificationKeys must not be null");
		verificationKeys = Map.copyOf(new LinkedHashMap<>(verificationKeys));
		if (!verificationKeys.containsKey(activeKeyId)) {
			throw new IllegalArgumentException("verificationKeys must contain active key");
		}
	}
}
