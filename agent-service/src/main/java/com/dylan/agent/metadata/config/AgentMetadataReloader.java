package com.dylan.agent.metadata.config;

import com.dylan.agent.metadata.domain.port.DomainMetadataPort;

import java.time.Clock;
import java.util.Objects;

/** 原子 reload seam。完整 candidate 转换归 D03，本类只负责发布语义。 */
public final class AgentMetadataReloader {

    private final AgentMetadataStore store;
    private final DomainMetadataPort domainMetadataPort;
    private final Clock clock;

    public AgentMetadataReloader(
            AgentMetadataStore store,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        this.store = Objects.requireNonNull(store);
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.clock = Objects.requireNonNull(clock);
    }

    public AgentMetadataBundle publishValidated(AgentMetadataBundle candidate) {
        Objects.requireNonNull(candidate, "candidate must not be null");
        AgentMetadataBundle current = store.current();
        if (current.bundleVersion().equals(candidate.bundleVersion())
                && !current.bundleDigest().equals(candidate.bundleDigest())) {
            throw new IllegalStateException("same metadata bundleVersion cannot change digest");
        }
        domainMetadataPort.assertCurrent(
                domainMetadataPort.validateReferences(
                        com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet.empty(),
                        clock.instant().plusSeconds(30)),
                clock.instant().plusSeconds(30));
        if (!store.compareAndSet(current, candidate)) {
            throw new IllegalStateException("concurrent metadata reload conflict");
        }
        return candidate;
    }
}
