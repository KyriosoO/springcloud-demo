package com.dylan.agent.capability.document.governance.emergency;

public enum DocumentEmergencyTargetType {
    CAPABILITY,
    CORPUS,
    PROFILE,
    INDEX_TARGET,
    PROVIDER_OPERATION,
    PROVIDER_BINDING;

    public static DocumentEmergencyTargetType fromWire(String value) {
        return valueOf(value);
    }
}
