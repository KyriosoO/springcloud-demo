package com.dylan.agent.service.application;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import com.dylan.agent.service.config.AgentIngressProperties;

import org.springframework.stereotype.Component;

@Component
public final class AgentRequestLimiter {
    private final AtomicInteger inFlight = new AtomicInteger();
    private final int maximum;

    public AgentRequestLimiter(AgentIngressProperties properties) {
        this.maximum = properties.maxInFlight();
    }

    public Lease tryAcquire() {
        while (true) {
            int current = inFlight.get();
            if (current >= maximum) {
                throw AgentPublicException.ingressCapacityExceeded();
            }
            if (inFlight.compareAndSet(current, current + 1)) {
                return new Lease(inFlight);
            }
        }
    }

    public int inFlight() {
        return inFlight.get();
    }

    public static final class Lease implements AutoCloseable {
        private final AtomicBoolean closed = new AtomicBoolean();
        private final AtomicInteger inFlight;

        private Lease(AtomicInteger inFlight) {
            this.inFlight = inFlight;
        }

        @Override
        public void close() {
            if (closed.compareAndSet(false, true)) {
                int remaining = inFlight.decrementAndGet();
                if (remaining < 0) {
                    throw new IllegalStateException("agent.limiter-release-invariant");
                }
            }
        }
    }
}
