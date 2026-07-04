package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class SecretMaterialJwtKeyProviderTest {

	@Test
	void buildsHmacSha256KeyFromBase64() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		SecretMaterialJwtKeyProvider provider =
				new SecretMaterialJwtKeyProvider(properties, new CompositeSecretMaterialProvider(properties));

		JwtKeySet keySet = provider.current();

		assertThat(keySet.activeKeyId()).isEqualTo(SecretTestSupport.ACTIVE);
		assertThat(keySet.activeKey().getAlgorithm()).isEqualTo("HmacSHA256");
		assertThat(keySet.activeKey().getEncoded()).hasSize(32);
		assertThat(keySet.verificationKeys()).containsKeys(SecretTestSupport.ACTIVE, SecretTestSupport.PREVIOUS);
	}
}
