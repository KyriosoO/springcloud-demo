package com.dylan.agent.metadata.config;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

/**
 * active security settings 的只读边界。
 */
public final class AgentSecuritySettingsRegistry {

    private final AgentMetadataStore store;
    private final AtomicReference<AgentSecuritySettings> current;

    public AgentSecuritySettingsRegistry(AgentMetadataStore store) {
        this.store = Objects.requireNonNull(store);
        this.current = null;
    }

    public AgentSecuritySettingsRegistry(AgentSecuritySettings initial) {
        this.store = null;
        this.current = new AtomicReference<>(Objects.requireNonNull(initial));
    }

    public AgentSecuritySettings current() {
        if (store != null) {
            return store.current().securitySettings();
        }
        return current.get();
    }

    public void replaceForReload(AgentSecuritySettings next) {
        if (store != null) {
            throw new IllegalStateException("store-backed security settings registry reads from metadata store");
        }
        current.set(Objects.requireNonNull(next));
    }
}
