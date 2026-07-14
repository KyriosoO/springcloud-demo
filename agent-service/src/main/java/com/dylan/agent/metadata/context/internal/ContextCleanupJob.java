package com.dylan.agent.metadata.context.internal;

import java.time.Clock;
import java.time.Instant;
import java.util.Objects;

/**
 * 每次 tick 使用可 reload security settings 的 Context cleanup trigger。
 */
public final class ContextCleanupJob {

    private final ContextRepository repository;
    private final ContextStorageProperties properties;
    private final Clock clock;
    private Instant nextEligibleAt;

    public ContextCleanupJob(
            ContextRepository repository,
            ContextStorageProperties properties,
            Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.properties = Objects.requireNonNull(properties);
        this.properties.validate();
        this.clock = Objects.requireNonNull(clock);
        this.nextEligibleAt = clock.instant();
    }

    public int tick() {
        Instant now = clock.instant();
        if (now.isBefore(nextEligibleAt)) {
            return 0;
        }
        int deleted = repository.deleteExpired(now, properties.getCleanupBatchSize());
        nextEligibleAt = now.plus(properties.getCleanupDelay());
        return deleted;
    }
}
