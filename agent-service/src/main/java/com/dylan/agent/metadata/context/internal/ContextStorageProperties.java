package com.dylan.agent.metadata.context.internal;

import org.springframework.boot.context.properties.ConfigurationProperties;

import java.time.Duration;
import java.util.Objects;

/** 只承载 Context 物理清理节奏，不参与可读授权或 TTL 计算。 */
@ConfigurationProperties(prefix = "agent.context")
public class ContextStorageProperties {

    private Duration cleanupDelay = Duration.ofHours(1);
    private int cleanupBatchSize = 100;

    public Duration getCleanupDelay() { return cleanupDelay; }
    public void setCleanupDelay(Duration cleanupDelay) { this.cleanupDelay = cleanupDelay; }
    public int getCleanupBatchSize() { return cleanupBatchSize; }
    public void setCleanupBatchSize(int cleanupBatchSize) { this.cleanupBatchSize = cleanupBatchSize; }

    public void validate() {
        Objects.requireNonNull(cleanupDelay, "agent.context.cleanup-delay must not be null");
        if (cleanupDelay.isNegative()) {
            throw new IllegalStateException("agent.context.cleanup-delay must not be negative");
        }
        if (cleanupBatchSize < 1 || cleanupBatchSize > 1000) {
            throw new IllegalStateException("agent.context.cleanup-batch-size must be 1-1000");
        }
    }
}
