package com.dylan.agent.metadata.policy.internal;

import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.policy.model.AgentPolicySnapshot;

import java.util.Objects;

/** 基于同一个 atomic metadata bundle 的只读 policy boundary。 */
public final class AgentPolicyConfiguration {

    private final AgentMetadataStore store;

    public AgentPolicyConfiguration(AgentMetadataStore store) {
        this.store = Objects.requireNonNull(store);
    }

    public AgentPolicySnapshot current() {
        return store.current().activePolicy();
    }

    public AgentPolicySnapshot requireVersion(String version) {
        AgentPolicySnapshot snapshot = store.current().policyVersionIndex().get(version);
        if (snapshot == null) {
            throw new IllegalStateException("unknown policy version: " + version);
        }
        return snapshot;
    }
}
