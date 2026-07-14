package com.dylan.common.security;

import java.util.Objects;

public final class SecretKeyRef {

	private final SecretPurpose purpose;
	private final String keyId;

	public SecretKeyRef(SecretPurpose purpose, String keyId) {
		this.purpose = Objects.requireNonNull(purpose, "purpose must not be null");
		this.keyId = requireNonBlank(keyId, "keyId");
	}

	public SecretPurpose purpose() {
		return purpose;
	}

	public String keyId() {
		return keyId;
	}

	@Override
	public String toString() {
		return "SecretKeyRef[purpose=" + purpose + ", keyId=" + keyId + "]";
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
