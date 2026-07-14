package com.dylan.esquery.document;

import java.time.Duration;

/** Offline rebuild 的 bounded operational policy。 */
public record DocumentRebuildWorkerPolicy(
        int pageSize, int maxBulkAttempts, Duration leaseDuration, Duration taskTimeout) {
    public DocumentRebuildWorkerPolicy {
        if (pageSize <= 0 || pageSize > 10_000 || maxBulkAttempts <= 0 || maxBulkAttempts > 10
                || leaseDuration == null || leaseDuration.isZero() || leaseDuration.isNegative()
                || taskTimeout == null || taskTimeout.isZero() || taskTimeout.isNegative()) {
            throw new IllegalArgumentException("document rebuild worker policy invalid");
        }
    }
}
