package com.dylan.agent.metadata.config;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.agent.metadata.policy.internal.AgentPolicyConfiguration;
import com.dylan.agent.metadata.profile.internal.AgentProfileRegistry;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

import java.time.Duration;
import java.util.Set;

import org.junit.jupiter.api.Test;

class AgentMetadataProductionBootstrapTest {

    @Test
    void bootstrapsStoreProfilePolicyAndSecurityFromOneBundle() {
        DefaultAgentMetadataBootstrap bootstrap = new DefaultAgentMetadataBootstrap(
                DomainMetadataTestSupport.agentProperties(),
                DomainMetadataTestSupport.properties());
        AgentMetadataStore store = new AgentMetadataStore(bootstrap.bootstrap());
        AgentProfileRegistry profileRegistry = new AgentProfileRegistry(store);
        AgentPolicyConfiguration policyConfiguration = new AgentPolicyConfiguration(store);
        AgentSecuritySettingsRegistry securitySettingsRegistry =
                new AgentSecuritySettingsRegistry(store.current().securitySettings());

        assertThat(profileRegistry.defaultRef().agentId()).isEqualTo("agent-default");
        assertThat(profileRegistry.defaultRef().expectedVersion()).contains("profile-v1");
        assertThat(policyConfiguration.current().domainSecurityConstraints().keySet())
                .containsExactlyInAnyOrder("employee", "transaction");
        assertThat(policyConfiguration.current().profileConstraints().get("agent-default").allowedCapabilityIds())
                .isEqualTo(Set.of("query.search", "query.preview", "aggregate.compute"));
        assertThat(profileRegistry.getRequired(profileRegistry.defaultRef()).allowedCapabilityIds())
                .containsExactlyInAnyOrder("query.search", "query.preview", "aggregate.compute");
        assertThat(policyConfiguration.current().capabilityConstraints())
                .containsKeys("query.search", "query.preview", "aggregate.compute");
        assertThat(securitySettingsRegistry.current()).isSameAs(store.current().securitySettings());
        assertThat(securitySettingsRegistry.current().globalMaxContextTtl()).isEqualTo(Duration.ofDays(7));
        assertThat(store.current().bundleDigest()).isNotBlank();
    }
}
