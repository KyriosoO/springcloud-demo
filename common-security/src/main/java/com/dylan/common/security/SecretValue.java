package com.dylan.common.security;

import java.util.Arrays;
import java.util.Objects;

public final class SecretValue {

	private final byte[] raw;

	public SecretValue(byte[] raw) {
		this.raw = Objects.requireNonNull(raw, "raw must not be null").clone();
	}

	public byte[] copyBytes() {
		return raw.clone();
	}

	public void destroy() {
		Arrays.fill(raw, (byte) 0);
	}

	@Override
	public String toString() {
		return "[REDACTED]";
	}
}
