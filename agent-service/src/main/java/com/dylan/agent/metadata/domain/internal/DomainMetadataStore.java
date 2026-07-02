package com.dylan.agent.metadata.domain.internal;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

/** 只读 D04 快照存储；D04 v1 在启动时发布一次。 */
public final class DomainMetadataStore {

    private final AtomicReference<DomainMetadataBundle> current;

    public DomainMetadataStore(DomainMetadataBundle initial) {
        this.current = new AtomicReference<>(Objects.requireNonNull(initial, "initial bundle must not be null"));
    }

    public DomainMetadataBundle current() {
        return current.get();
    }
}
