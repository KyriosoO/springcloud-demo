package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;

class PurposeScopedJwtKeyProviderTest {

	@Test
	void resolvesIndependentActiveAndPreviousAgentServiceKeys() {
		SecretProperties.PurposeProperties properties = new SecretProperties.PurposeProperties("ACTIVE");
		properties.setPreviousKeyIds(java.util.List.of("PREVIOUS"));
		properties.setKeys(Map.of(
				"ACTIVE", new SecretProperties.KeyProperties(),
				"PREVIOUS", new SecretProperties.KeyProperties()));
		SecretMaterialProvider materials = ref -> {
			byte fill = (byte) ("ACTIVE".equals(ref.keyId()) ? 'A' : 'B');
			byte[] raw = new byte[32];
			java.util.Arrays.fill(raw, fill);
			return new SecretMaterial(ref.purpose(), ref.keyId(), new SecretValue(raw),
					SecretSourceType.CONFIG);
		};

		JwtKeySet keys = new PurposeScopedJwtKeyProvider(
				SecretPurpose.AGENT_SERVICE_JWT, properties, materials).current();

		assertThat(keys.activeKeyId()).isEqualTo("ACTIVE");
		assertThat(keys.verificationKeys()).containsOnlyKeys("ACTIVE", "PREVIOUS");
		assertThat(keys.verificationKeys().get("ACTIVE").getEncoded())
				.isNotEqualTo(keys.verificationKeys().get("PREVIOUS").getEncoded());
	}
}
