package com.dylan.agent.service.contract;

import com.fasterxml.jackson.annotation.JsonValue;
import com.fasterxml.jackson.annotation.JsonCreator;

public enum FailureSource {
    CORE("core"),
    CAPABILITY("capability"),
    DOWNSTREAM("downstream"),
    POLICY("policy");

    private final String wireValue;

    FailureSource(String wireValue) {
        this.wireValue = wireValue;
    }

    @JsonValue
    public String wireValue() {
        return wireValue;
    }

    @JsonCreator
    public static FailureSource fromWireValue(String value) {
        for (FailureSource source : values()) {
            if (source.wireValue.equals(value)) {
                return source;
            }
        }
        throw new IllegalArgumentException("agent.failure-source-invalid");
    }
}
