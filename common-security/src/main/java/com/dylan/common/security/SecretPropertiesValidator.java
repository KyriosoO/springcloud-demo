package com.dylan.common.security;

import java.util.LinkedHashSet;
import java.util.Objects;
import java.util.Set;
import java.util.regex.Pattern;

import org.springframework.core.env.Environment;
import org.springframework.core.env.Profiles;

public final class SecretPropertiesValidator {

	private static final Pattern KEY_ID = Pattern.compile("[A-Za-z0-9_]{1,64}");

	private SecretPropertiesValidator() {
	}

	public static void validate(SecretProperties properties, Environment environment) {
		validateJwt(properties, environment);
		validateAgentPayload(properties, environment);
	}

	public static void validateJwt(SecretProperties properties, Environment environment) {
		Objects.requireNonNull(properties, "properties must not be null");
		validateSources(properties);
		validateProductionSourceOrder(properties, environment);
		validatePurpose("jwt", properties.getJwt());
		validateConfigValuePolicy(properties, properties.getJwt(), environment);
		validatePurposeIsolation(properties);
	}

	public static void validateAgentPayload(SecretProperties properties, Environment environment) {
		Objects.requireNonNull(properties, "properties must not be null");
		validateSources(properties);
		validateProductionSourceOrder(properties, environment);
		validatePurpose("agent-payload", properties.getAgentPayload());
		validateConfigValuePolicy(properties, properties.getAgentPayload(), environment);
		validatePurposeIsolation(properties);
	}

	private static void validatePurposeIsolation(SecretProperties properties) {
		for (SecretProperties.KeyProperties jwt : properties.getJwt().getKeys().values()) {
			for (SecretProperties.KeyProperties payload : properties.getAgentPayload().getKeys().values()) {
				if (sameNonBlank(jwt.getEnv(), payload.getEnv())
						|| sameNonBlank(jwt.getValue(), payload.getValue())) {
					throw new SecretMaterialException(
							"JWT and agent payload secret bindings must be purpose-isolated");
				}
			}
		}
	}

	private static boolean sameNonBlank(String left, String right) {
		return left != null && right != null
				&& !left.isBlank() && !right.isBlank()
				&& left.trim().equals(right.trim());
	}

	public static void validateKeyId(String keyId) {
		if (keyId == null || !KEY_ID.matcher(keyId.trim()).matches()) {
			throw new SecretMaterialException("Invalid key id");
		}
	}

	private static void validateSources(SecretProperties properties) {
		if (properties.getSourceOrder().isEmpty()) {
			throw new SecretMaterialException("common.security.secrets.source-order must not be empty");
		}
		if (properties.getSourceOrder().stream().anyMatch(Objects::isNull)) {
			throw new SecretMaterialException("common.security.secrets.source-order must not contain null");
		}
	}

	private static void validateProductionSourceOrder(SecretProperties properties, Environment environment) {
		if (isProduction(environment) && properties.getSourceOrder().get(0) == SecretSourceType.CONFIG) {
			throw new SecretMaterialException(
					"common.security.secrets.source-order must not prefer config in production profiles");
		}
	}

	private static void validatePurpose(String name, SecretProperties.PurposeProperties purpose) {
		if (purpose == null) {
			throw new SecretMaterialException("Missing secret purpose config: " + name);
		}
		validateKeyId(purpose.getActiveKeyId());
		Set<String> ids = new LinkedHashSet<>();
		ids.add(purpose.getActiveKeyId().trim());
		for (String previous : purpose.getPreviousKeyIds()) {
			validateKeyId(previous);
			ids.add(previous.trim());
		}
		for (String keyId : ids) {
			if (!purpose.getKeys().containsKey(keyId)) {
				throw new SecretMaterialException("Missing secret key config for " + name + ":" + keyId, null, true);
			}
		}
	}

	private static void validateConfigValuePolicy(
			SecretProperties properties,
			SecretProperties.PurposeProperties purpose,
			Environment environment) {
		if (containsConfigValue(purpose) && !properties.isAllowConfigValues()) {
			throw new SecretMaterialException("Config secret values are disabled");
		}
		if (containsConfigValue(purpose) && isProduction(environment)) {
			throw new SecretMaterialException("Config secret values are forbidden in production profiles");
		}
	}

	private static boolean containsConfigValue(SecretProperties.PurposeProperties purpose) {
		return purpose != null && purpose.getKeys().values().stream()
				.anyMatch(key -> key.getValue() != null && !key.getValue().isBlank());
	}

	private static boolean isProduction(Environment environment) {
		return environment != null && environment.acceptsProfiles(Profiles.of("prod", "production"));
	}
}
