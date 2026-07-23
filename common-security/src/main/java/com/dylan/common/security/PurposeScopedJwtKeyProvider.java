package com.dylan.common.security;

import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

/**
 * Resolves a JWT key set for one explicit secret purpose.
 */
public final class PurposeScopedJwtKeyProvider implements JwtKeyProvider {

	private final SecretPurpose purpose;
	private final SecretProperties.PurposeProperties properties;
	private final SecretMaterialProvider materialProvider;
	private volatile JwtKeySet cached;

	public PurposeScopedJwtKeyProvider(SecretPurpose purpose,
			SecretProperties.PurposeProperties properties,
			SecretMaterialProvider materialProvider) {
		this.purpose = Objects.requireNonNull(purpose);
		this.properties = Objects.requireNonNull(properties);
		this.materialProvider = Objects.requireNonNull(materialProvider);
		if (purpose == SecretPurpose.AGENT_PAYLOAD) {
			throw new IllegalArgumentException("AGENT_PAYLOAD is not a JWT signing purpose");
		}
	}

	@Override
	public JwtKeySet current() {
		JwtKeySet result = cached;
		if (result == null) {
			synchronized (this) {
				result = cached;
				if (result == null) {
					result = build();
					cached = result;
				}
			}
		}
		return result;
	}

	private JwtKeySet build() {
		String activeKeyId = properties.getActiveKeyId();
		Map<String, SecretKey> verificationKeys = new LinkedHashMap<>();
		SecretKey activeKey = resolve(activeKeyId);
		verificationKeys.put(activeKeyId, activeKey);
		for (String previousKeyId : properties.getPreviousKeyIds()) {
			verificationKeys.put(previousKeyId, resolve(previousKeyId));
		}
		return new JwtKeySet(activeKeyId, activeKey, verificationKeys);
	}

	private SecretKey resolve(String keyId) {
		if (!properties.getKeys().containsKey(keyId)) {
			throw new SecretMaterialException("Missing JWT key config for " + purpose + ":" + keyId, null, true);
		}
		SecretMaterial material = materialProvider.requireSecret(new SecretKeyRef(purpose, keyId));
		byte[] raw = material.secretValue().copyBytes();
		try {
			if (raw.length < 32) {
				throw new SecretMaterialException("JWT HMAC key must be at least 32 bytes for keyId " + keyId);
			}
			return new SecretKeySpec(raw, "HmacSHA256");
		} finally {
			Arrays.fill(raw, (byte) 0);
			material.secretValue().destroy();
		}
	}
}
