package com.dylan.agent.metadata.domain.internal;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

/** Read-only D04 snapshot store. D04 v1 publishes once during startup. */
public final class DomainMetadataStore {

    private final AtomicReference<DomainMetadataBundle> current;

    public DomainMetadataStore(DomainMetadataBundle initial) {
        this.current = new AtomicReference<>(Objects.requireNonNull(initial, "initial bundle must not be null"));
    }

    public DomainMetadataBundle current() {
        return current.get();
    }
}
