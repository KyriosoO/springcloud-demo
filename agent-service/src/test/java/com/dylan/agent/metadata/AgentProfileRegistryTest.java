package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.profile.internal.AgentProfileRegistry;

class AgentProfileRegistryTest {
    @Test
    void resolvesDefaultRefWithExactActiveVersion() {
        AgentProfileRegistry registry = new AgentProfileRegistry(
                new AgentMetadataStore(MetadataTestSupport.bundle("bundle-v1", "digest-v1")));

        assertThat(registry.defaultRef().agentId()).isEqualTo("agent-default");
        assertThat(registry.defaultRef().expectedVersion()).contains("profile-v1");
    }
}
