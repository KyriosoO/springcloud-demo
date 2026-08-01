package com.dylan.agent.service.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;

import com.dylan.agent.service.config.AgentIngressProperties;

import org.junit.jupiter.api.Test;

class AgentRequestLimiterTest {

    @Test
    void rejectsBeyondLimitAndReleasesExactlyOnce() {
        AgentRequestLimiter limiter = new AgentRequestLimiter(
                new AgentIngressProperties(4096, 32768, 16384, 1,
                        Duration.ofSeconds(60), Duration.ofMillis(500)));
        AgentRequestLimiter.Lease lease = limiter.tryAcquire();

        assertThatThrownBy(limiter::tryAcquire).isInstanceOf(AgentPublicException.class);
        lease.close();
        lease.close();

        assertThat(limiter.inFlight()).isZero();
    }
}
