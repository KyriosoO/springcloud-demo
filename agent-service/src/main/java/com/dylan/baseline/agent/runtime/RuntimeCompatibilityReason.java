package com.dylan.baseline.agent.runtime;

public enum RuntimeCompatibilityReason {
    COMPATIBLE,
    METADATA_INVALID,
    VERSION_MISMATCH,
    FINGERPRINT_MISMATCH,
    CAPABILITY_MISSING
}
