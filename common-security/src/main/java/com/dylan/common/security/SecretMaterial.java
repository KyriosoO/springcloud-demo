package com.dylan.common.security;

import java.util.Objects;

public final class SecretMaterial {

	private final SecretPurpose purpose;
	private final String keyId;
	private final SecretValue secretValue;
	private final SecretSourceType source;

	public SecretMaterial(SecretPurpose purpose, String keyId, SecretValue secretValue, SecretSourceType source) {
		this.purpose = Objects.requireNonNull(purpose, "purpose must not be null");
		this.keyId = requireNonBlank(keyId, "keyId");
		this.secretValue = Objects.requireNonNull(secretValue, "secretValue must not be null");
		this.source = Objects.requireNonNull(source, "source must not be null");
	}

	public SecretPurpose purpose() {
		return purpose;
	}

	public String keyId() {
		return keyId;
	}

	public SecretValue secretValue() {
		return secretValue;
	}

	public SecretSourceType source() {
		return source;
	}

	@Override
	public String toString() {
		return "SecretMaterial[purpose=" + purpose + ", keyId=" + keyId + ", source=" + source
				+ ", secretValue=[REDACTED]]";
	}

	private static String requireNonBlank(String value, String name) {
		Objects.requireNonNull(value, name + " must not be null");
		String normalized = value.trim();
		if (normalized.isEmpty()) {
			throw new IllegalArgumentException(name + " must not be blank");
		}
		return normalized;
	}
}
