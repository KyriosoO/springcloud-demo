package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;

class SecretPropertiesValidatorTest {

	@Test
	void rejectsConfigSecretInProd() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		properties.setSourceOrder(java.util.List.of(SecretSourceType.ENVIRONMENT, SecretSourceType.CONFIG));
		MockEnvironment environment = new MockEnvironment().withProperty("spring.profiles.active", "prod");

		assertThatThrownBy(() -> SecretPropertiesValidator.validate(properties, environment))
				.isInstanceOf(SecretMaterialException.class)
				.hasMessageContaining("production");
	}

	@Test
	void rejectsConfigPreferredSourceOrderInProd() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		properties.getJwt().getKeys().values().forEach(key -> key.setValue(""));
		properties.getAgentPayload().getKeys().values().forEach(key -> key.setValue(""));
		MockEnvironment environment = new MockEnvironment().withProperty("spring.profiles.active", "prod");

		assertThatThrownBy(() -> SecretPropertiesValidator.validateJwt(properties, environment))
				.isInstanceOf(SecretMaterialException.class)
				.hasMessageContaining("source-order");
	}

	@Test
	void rejectsConfigSecretWhenDisabled() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		properties.setAllowConfigValues(false);

		assertThatThrownBy(() -> SecretPropertiesValidator.validate(properties, new MockEnvironment()))
				.isInstanceOf(SecretMaterialException.class)
				.hasMessageContaining("disabled");
	}

	@Test
	void acceptsDefaultEnvFallbackKeyConfig() {
		SecretProperties properties = new SecretProperties();

		SecretPropertiesValidator.validateJwt(properties, new MockEnvironment());
		SecretPropertiesValidator.validateAgentPayload(properties, new MockEnvironment());
	}

	@Test
	void jwtValidationDoesNotRequireAgentPayloadKeyConfig() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		properties.getAgentPayload().getKeys().clear();

		SecretPropertiesValidator.validateJwt(properties, new MockEnvironment());
	}

	@Test
	void agentPayloadValidationRequiresAgentPayloadKeyConfig() {
		SecretProperties properties = SecretTestSupport.jwtOnlyProperties();
		properties.getAgentPayload().getKeys().clear();

		assertThatThrownBy(() -> SecretPropertiesValidator.validateAgentPayload(properties, new MockEnvironment()))
				.isInstanceOf(SecretMaterialException.class)
				.hasMessageContaining("agent-payload");
	}
}
