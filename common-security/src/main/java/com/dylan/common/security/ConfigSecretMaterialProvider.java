package com.dylan.common.security;

import java.util.Base64;

public final class ConfigSecretMaterialProvider implements SecretMaterialProvider {

	@Override
	public SecretMaterial requireSecret(SecretKeyRef ref) {
		String encoded = ref.configValue();
		if (encoded == null || encoded.isBlank()) {
			throw new SecretMaterialException("Missing config secret for " + ref.purpose() + ":" + ref.keyId(), null,
					true);
		}
		return decode(ref, encoded, SecretSourceType.CONFIG);
	}

	static SecretMaterial decode(SecretKeyRef ref, String encoded, SecretSourceType source) {
		try {
			return new SecretMaterial(ref.purpose(), ref.keyId(),
					new SecretValue(Base64.getDecoder().decode(encoded.trim())), source);
		} catch (IllegalArgumentException ex) {
			throw new SecretMaterialException("Invalid Base64 secret for " + ref.purpose() + ":" + ref.keyId(), ex);
		}
	}
}
