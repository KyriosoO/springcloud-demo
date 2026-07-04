package com.dylan.common.security;

import java.util.Objects;

public final class SecretKeyRef {

	private final SecretPurpose purpose;
	private final String keyId;
	private final String envName;
	private final String configValue;

	public SecretKeyRef(SecretPurpose purpose, String keyId, String envName, String configValue) {
		this.purpose = Objects.requireNonNull(purpose, "purpose must not be null");
		this.keyId = requireNonBlank(keyId, "keyId");
		this.envName = normalizeNullable(envName);
		this.configValue = normalizeNullable(configValue);
	}

	public SecretPurpose purpose() {
		return purpose;
	}

	public String keyId() {
		return keyId;
	}

	public String envName() {
		return envName;
	}

	public String configValue() {
		return configValue;
	}

	@Override
	public String toString() {
		return "SecretKeyRef[purpose=" + purpose + ", keyId=" + keyId + ", envName=" + envName
				+ ", configValue=[REDACTED]]";
	}

	private static String requireNonBlank(String value, String name) {
		Objects.requireNonNull(value, name + " must not be null");
		String normalized = value.trim();
		if (normalized.isEmpty()) {
			throw new IllegalArgumentException(name + " must not be blank");
		}
		return normalized;
	}

	private static String normalizeNullable(String value) {
		if (value == null) {
			return "";
		}
		return value.trim();
	}
}
