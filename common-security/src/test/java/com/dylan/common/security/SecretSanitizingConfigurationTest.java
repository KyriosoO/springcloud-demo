package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.boot.actuate.endpoint.SanitizableData;
import org.springframework.boot.actuate.endpoint.SanitizingFunction;
import org.springframework.core.env.MapPropertySource;

class SecretSanitizingConfigurationTest {

	@Test
	void masksConfiguredSecretValues() {
		SanitizingFunction function = new SecretSanitizingConfiguration().secretSanitizingFunction();
		MapPropertySource source = new MapPropertySource("test", Map.of());
		SanitizableData data = new SanitizableData(
				source,
				"common.security.secrets.jwt.keys.ACTIVE.value",
				SecretTestSupport.ACTIVE_SECRET);

		assertThat(function.apply(data).getValue()).isEqualTo(SanitizableData.SANITIZED_VALUE);
	}

	@Test
	void masksProviderTokenAndKeyLikeConfigNames() {
		SanitizingFunction function = new SecretSanitizingConfiguration().secretSanitizingFunction();
		MapPropertySource source = new MapPropertySource("test", Map.of());

		assertThat(function.apply(new SanitizableData(
				source,
				"external.provider.token",
				"token-value")).getValue()).isEqualTo(SanitizableData.SANITIZED_VALUE);
		assertThat(function.apply(new SanitizableData(
				source,
				"external.provider.api-key",
				"key-value")).getValue()).isEqualTo(SanitizableData.SANITIZED_VALUE);
	}
}
