package com.dylan.agent.employee.api.model;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

public enum AgentEmployeeField {
	POSITION("position"),
	WORK_BASE_SI("workBaseSi");

	private final String jsonName;

	AgentEmployeeField(String jsonName) {
		this.jsonName = jsonName;
	}

	@JsonValue
	public String jsonName() { return jsonName; }

	@JsonCreator
	public static AgentEmployeeField fromJson(String value) {
		for (AgentEmployeeField field : values()) {
			if (field.jsonName.equals(value)) {
				return field;
			}
		}
		throw new IllegalArgumentException("Unknown employee field");
	}
}
