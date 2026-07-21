package com.dylan.agent.metadata.config;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

/** 包级原子 holder；消费者读取一个不可变 bundle snapshot。 */
public final class AgentMetadataStore {

    private final AtomicReference<AgentMetadataBundle> current;

    public AgentMetadataStore(AgentMetadataBundle initialBundle) {
        this.current = new AtomicReference<>(Objects.requireNonNull(initialBundle, "initialBundle must not be null"));
    }

    public AgentMetadataBundle current() {
        return current.get();
    }

    public boolean compareAndSet(AgentMetadataBundle expected, AgentMetadataBundle candidate) {
        return current.compareAndSet(
                Objects.requireNonNull(expected, "expected must not be null"),
                Objects.requireNonNull(candidate, "candidate must not be null"));
    }
}
