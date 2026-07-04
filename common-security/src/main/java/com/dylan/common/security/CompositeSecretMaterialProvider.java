package com.dylan.common.security;

import java.util.EnumMap;
import java.util.Map;
import java.util.Objects;

public final class CompositeSecretMaterialProvider implements SecretMaterialProvider {

	private final SecretProperties properties;
	private final Map<SecretSourceType, SecretMaterialProvider> providers;

	public CompositeSecretMaterialProvider(SecretProperties properties) {
		this(properties, new ConfigSecretMaterialProvider(), new EnvironmentSecretMaterialProvider());
	}

	CompositeSecretMaterialProvider(
			SecretProperties properties,
			ConfigSecretMaterialProvider configProvider,
			EnvironmentSecretMaterialProvider environmentProvider) {
		this.properties = Objects.requireNonNull(properties, "properties must not be null");
		this.providers = new EnumMap<>(SecretSourceType.class);
		this.providers.put(SecretSourceType.CONFIG, Objects.requireNonNull(configProvider));
		this.providers.put(SecretSourceType.ENVIRONMENT, Objects.requireNonNull(environmentProvider));
	}

	@Override
	public SecretMaterial requireSecret(SecretKeyRef ref) {
		SecretMaterialException lastMissing = null;
		for (SecretSourceType source : properties.getSourceOrder()) {
			SecretMaterialProvider provider = providers.get(source);
			if (provider == null) {
				continue;
			}
			try {
				return provider.requireSecret(ref);
			} catch (SecretMaterialException ex) {
				if (!ex.isMissing()) {
					throw ex;
				}
				lastMissing = ex;
			}
		}
		if (lastMissing != null) {
			throw lastMissing;
		}
		throw new SecretMaterialException("No secret provider configured for " + ref.purpose() + ":" + ref.keyId(),
				null, true);
	}
}
