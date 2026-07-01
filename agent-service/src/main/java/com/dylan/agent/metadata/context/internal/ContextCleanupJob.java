package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;

import java.time.Clock;
import java.time.Instant;
import java.util.Objects;

/**
 * Context cleanup trigger using reloadable security settings per tick.
 */
public final class ContextCleanupJob {

    private final ContextRepository repository;
    private final AgentSecuritySettingsRegistry settingsRegistry;
    private final Clock clock;
    private Instant nextEligibleAt;

    public ContextCleanupJob(
            ContextRepository repository,
            AgentSecuritySettingsRegistry settingsRegistry,
            Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.settingsRegistry = Objects.requireNonNull(settingsRegistry);
        this.clock = Objects.requireNonNull(clock);
        this.nextEligibleAt = clock.instant();
    }

    public int tick() {
        Instant now = clock.instant();
        if (now.isBefore(nextEligibleAt)) {
            return 0;
        }
        var settings = settingsRegistry.current();
        int deleted = repository.deleteExpired(now, settings.contextCleanupBatchSize());
        nextEligibleAt = now.plus(settings.contextCleanupDelay());
        return deleted;
    }
}
