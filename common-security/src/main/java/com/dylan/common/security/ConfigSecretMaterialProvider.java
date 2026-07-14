package com.dylan.common.security;

import java.util.Base64;
import java.util.Arrays;
import java.util.Objects;
import java.util.function.Function;

public final class ConfigSecretMaterialProvider implements SecretMaterialProvider {
	private final Function<SecretKeyRef, String> valueLocator;

	public ConfigSecretMaterialProvider(Function<SecretKeyRef, String> valueLocator) {
		this.valueLocator = Objects.requireNonNull(valueLocator, "valueLocator must not be null");
	}

	@Override
	public SecretMaterial requireSecret(SecretKeyRef ref) {
		String encoded = valueLocator.apply(ref);
		if (encoded == null || encoded.isBlank()) {
			throw new SecretMaterialException("Missing config secret for " + ref.purpose() + ":" + ref.keyId(), null,
					true);
		}
		return decode(ref, encoded, SecretSourceType.CONFIG);
	}

	static SecretMaterial decode(SecretKeyRef ref, String encoded, SecretSourceType source) {
		byte[] decoded = null;
		try {
			decoded = Base64.getDecoder().decode(encoded.trim());
			return new SecretMaterial(ref.purpose(), ref.keyId(),
					new SecretValue(decoded), source);
		} catch (IllegalArgumentException ex) {
			throw new SecretMaterialException("Invalid Base64 secret for " + ref.purpose() + ":" + ref.keyId(), ex);
		} finally {
			if (decoded != null) {
				Arrays.fill(decoded, (byte) 0);
			}
		}
	}
}
