package com.dylan.agent.metadata.context;

import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.context.internal.ContextCleanupJob;
import com.dylan.agent.metadata.context.internal.ContextRecordEntity;
import com.dylan.agent.metadata.context.internal.ContextRepository;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class ContextCleanupJobTest {

    @Test
    void tickUsesCurrentReloadableCleanupSettings() {
        MutableClock clock = new MutableClock(Instant.parse("2026-07-01T00:00:00Z"));
        RecordingRepository repository = new RecordingRepository();
        AgentSecuritySettingsRegistry settings = new AgentSecuritySettingsRegistry(
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ofSeconds(30), 5, "ACTIVE"));
        ContextCleanupJob job = new ContextCleanupJob(repository, settings, clock);

        assertThat(job.tick()).isEqualTo(5);
        assertThat(repository.lastLimit).isEqualTo(5);
        assertThat(job.tick()).isZero();

        settings.replaceForReload(new AgentSecuritySettings(
                Duration.ofHours(1), Duration.ofSeconds(10), 9, "ACTIVE"));
        clock.current = clock.current.plusSeconds(30);

        assertThat(job.tick()).isEqualTo(9);
        assertThat(repository.lastLimit).isEqualTo(9);
    }

    private static final class RecordingRepository implements ContextRepository {
        private int lastLimit;

        @Override
        public void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion) {
        }

        @Override
        public void markConversationUnreadable(ConversationScope scope, Instant now) {
        }

        @Override
        public int deleteExpired(Instant cutoff, int limit) {
            this.lastLimit = limit;
            return limit;
        }
    }

    private static final class MutableClock extends Clock {
        private Instant current;

        private MutableClock(Instant current) {
            this.current = current;
        }

        @Override
        public ZoneOffset getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(java.time.ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            return current;
        }
    }
}
