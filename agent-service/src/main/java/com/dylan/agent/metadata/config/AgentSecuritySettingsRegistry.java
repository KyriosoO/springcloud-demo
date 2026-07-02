package com.dylan.agent.metadata.config;

import java.util.Objects;
import java.util.concurrent.atomic.AtomicReference;

/**
 * active security settings 的只读边界。
 */
public final class AgentSecuritySettingsRegistry {

    private final AtomicReference<AgentSecuritySettings> current;

    public AgentSecuritySettingsRegistry(AgentSecuritySettings initial) {
        this.current = new AtomicReference<>(Objects.requireNonNull(initial));
    }

    public AgentSecuritySettings current() {
        return current.get();
    }

    public void replaceForReload(AgentSecuritySettings next) {
        current.set(Objects.requireNonNull(next));
    }
}
