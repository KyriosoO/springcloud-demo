package com.dylan.agent.kernel.port.model;

/**
 * Closed CAS expectation for approved context persistence.
 *
 * <p>D02_03 requires an explicit absent-or-existing union instead of nullable
 * fields. {@link #targetVersion()} is the version that will be written when
 * the CAS succeeds, and is also part of the context payload AAD.</p>
 */
public sealed interface ExpectedContextVersion
        permits ExpectedContextVersion.ExpectedAbsent, ExpectedContextVersion.ExpectedVersion {

    static ExpectedContextVersion absent() {
        return new ExpectedAbsent();
    }

    static ExpectedContextVersion version(long recordVersion) {
        return new ExpectedVersion(recordVersion);
    }

    boolean expectsAbsent();

    long targetVersion();

    record ExpectedAbsent() implements ExpectedContextVersion {
        @Override
        public boolean expectsAbsent() {
            return true;
        }

        @Override
        public long targetVersion() {
            return 0L;
        }
    }

    record ExpectedVersion(long recordVersion) implements ExpectedContextVersion {
        public ExpectedVersion {
            if (recordVersion < 0) {
                throw new IllegalArgumentException("recordVersion must be non-negative");
            }
            if (recordVersion == Long.MAX_VALUE) {
                throw new IllegalArgumentException("recordVersion target would overflow");
            }
        }

        @Override
        public boolean expectsAbsent() {
            return false;
        }

        @Override
        public long targetVersion() {
            return recordVersion + 1;
        }
    }
}
