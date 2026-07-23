package com.dylan.authcenter.agent.authorization.api;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public final class SensitiveBearerToken {

	private final String value;

	@JsonCreator(mode = JsonCreator.Mode.DELEGATING)
	public SensitiveBearerToken(String value) {
		this.value = value;
	}

	@JsonValue
	public String value() {
		return value;
	}

	@Override
	public String toString() {
		return "[REDACTED]";
	}
}
