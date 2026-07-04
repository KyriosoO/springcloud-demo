package com.dylan.common.security;

public class SecretMaterialException extends RuntimeException {

	private final boolean missing;

	public SecretMaterialException(String message) {
		this(message, null, false);
	}

	public SecretMaterialException(String message, Throwable cause) {
		this(message, cause, false);
	}

	public SecretMaterialException(String message, Throwable cause, boolean missing) {
		super(message, cause);
		this.missing = missing;
	}

	public boolean isMissing() {
		return missing;
	}
}
