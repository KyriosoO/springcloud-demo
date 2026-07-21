package com.dylan.agent.kernel.port.model;

/**
 * 已批准 Context 持久化使用的封闭 CAS 预期。
 *
 * <p>D02_03 要求使用显式 absent-or-existing union，而不是 nullable 字段。
 * {@link #targetVersion()} 是 CAS 成功后写入的版本，也是 context payload AAD 的一部分。</p>
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
