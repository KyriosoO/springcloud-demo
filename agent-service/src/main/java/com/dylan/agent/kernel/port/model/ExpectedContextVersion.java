package com.dylan.agent.kernel.port.model;

/**
 * CAS expectation for approved context persistence.
 */
public record ExpectedContextVersion(Long recordVersion) {

    public ExpectedContextVersion {
        if (recordVersion != null && recordVersion < 0) {
            throw new IllegalArgumentException("recordVersion must be non-negative");
        }
    }

    public static ExpectedContextVersion absent() {
        return new ExpectedContextVersion(null);
    }

    public static ExpectedContextVersion version(long recordVersion) {
        return new ExpectedContextVersion(recordVersion);
    }

    public boolean expectsAbsent() {
        return recordVersion == null;
    }
}
