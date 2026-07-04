package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;

class CompositeSecretMaterialProviderTest {

	@Test
	void resolvesBySourceOrder() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		EnvironmentSecretMaterialProvider environmentProvider =
				new EnvironmentSecretMaterialProvider(name -> Map.of("JWT_ENV", SecretTestSupport.PREVIOUS_SECRET)
						.get(name));
		SecretProperties.KeyProperties key = properties.getJwt().getKeys().get(SecretTestSupport.ACTIVE);
		key.setEnv("JWT_ENV");
		key.setValue(SecretTestSupport.ACTIVE_SECRET);

		CompositeSecretMaterialProvider provider = new CompositeSecretMaterialProvider(
				properties,
				new ConfigSecretMaterialProvider(),
				environmentProvider);

		SecretMaterial material = provider.requireSecret(new SecretKeyRef(
				SecretPurpose.JWT_HMAC,
				SecretTestSupport.ACTIVE,
				key.getEnv(),
				key.getValue()));

		assertThat(material.source()).isEqualTo(SecretSourceType.CONFIG);
		assertThat(material.secretValue().copyBytes()).containsOnly((byte) 1);
	}
}
