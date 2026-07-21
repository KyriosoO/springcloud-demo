package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.policy.internal.AgentPolicyConfiguration;

class AgentPolicyConfigurationTest {
    @Test
    void readsCurrentAndRetainedPolicyFromSameBundle() {
        AgentPolicyConfiguration configuration = new AgentPolicyConfiguration(
                new AgentMetadataStore(MetadataTestSupport.bundle("bundle-v1", "digest-v1")));

        assertThat(configuration.current().policyVersion()).isEqualTo("policy-v1");
        assertThat(configuration.requireVersion("policy-v1")).isSameAs(configuration.current());
    }
}
