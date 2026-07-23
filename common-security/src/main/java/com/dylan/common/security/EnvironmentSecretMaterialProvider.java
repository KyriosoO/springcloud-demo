package com.dylan.common.security;

import java.util.Locale;
import java.util.Objects;
import java.util.function.Function;

public final class EnvironmentSecretMaterialProvider implements SecretMaterialProvider {

	private final Function<String, String> secretLookup;
	private final Function<SecretKeyRef, String> envNameLocator;

	public EnvironmentSecretMaterialProvider() {
		this(System::getenv, ref -> "");
	}

	public EnvironmentSecretMaterialProvider(Function<String, String> secretLookup) {
		this(secretLookup, ref -> "");
	}

	public EnvironmentSecretMaterialProvider(
			Function<String, String> secretLookup,
			Function<SecretKeyRef, String> envNameLocator) {
		this.secretLookup = Objects.requireNonNull(secretLookup, "secretLookup must not be null");
		this.envNameLocator = Objects.requireNonNull(envNameLocator, "envNameLocator must not be null");
	}

	@Override
	public SecretMaterial requireSecret(SecretKeyRef ref) {
		String envName = envNameLocator.apply(ref);
		if (envName == null || envName.isBlank()) {
			envName = defaultEnvName(ref);
		}
		String encoded = secretLookup.apply(envName);
		if (encoded == null || encoded.isBlank()) {
			throw new SecretMaterialException("Missing environment secret: " + envName, null, true);
		}
		return ConfigSecretMaterialProvider.decode(ref, encoded, SecretSourceType.ENVIRONMENT);
	}

	private static String defaultEnvName(SecretKeyRef ref) {
		String normalizedKeyId = ref.keyId().trim().toUpperCase(Locale.ROOT);
		return "COMMON_SECURITY_JWT_HMAC_KEY_" + normalizedKeyId;
	}
}
