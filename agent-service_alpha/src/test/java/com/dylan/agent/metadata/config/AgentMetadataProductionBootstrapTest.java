package com.dylan.agent.metadata.config;

import static org.assertj.core.api.Assertions.assertThat;
import com.dylan.agent.metadata.policy.internal.AgentPolicyConfiguration;
import com.dylan.agent.metadata.profile.internal.AgentProfileRegistry;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import com.dylan.agent.capability.document.profile.DocumentProfileProperties;

import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;

class AgentMetadataProductionBootstrapTest {

    @Test
    void bootstrapsStoreProfileAndPolicyFromOneBundle() {
        DefaultAgentMetadataBootstrap bootstrap = new DefaultAgentMetadataBootstrap(
                DomainMetadataTestSupport.agentProperties(), documentAssets());
        AgentMetadataStore store = new AgentMetadataStore(bootstrap.bootstrap());
        AgentProfileRegistry profileRegistry = new AgentProfileRegistry(store);
        AgentPolicyConfiguration policyConfiguration = new AgentPolicyConfiguration(store);
        assertThat(profileRegistry.defaultRef().agentId()).isEqualTo("agent-default");
        assertThat(profileRegistry.defaultRef().expectedVersion()).contains("profile-v1");
        assertThat(policyConfiguration.current().domainSecurityConstraints().keySet())
                .containsExactlyInAnyOrder("employee", "transaction");
        assertThat(policyConfiguration.current().profileConstraints().get("agent-default").allowedCapabilityIds())
                .contains("query.search", "query.preview", "aggregate.compute",
                        "document.search", "document.answer", "document.summarize");
        assertThat(profileRegistry.getRequired(profileRegistry.defaultRef()).allowedCapabilityIds())
                .contains("query.search", "query.preview", "aggregate.compute",
                        "document.search", "document.answer", "document.summarize");
        assertThat(policyConfiguration.current().capabilityConstraints())
                .containsKeys("query.search", "query.preview", "aggregate.compute",
                        "document.search", "document.answer", "document.summarize");
        assertThat(store.current().bundleDigest()).isNotBlank();
    }

    @Test
    void digestIsStableForSameReviewedBundleInputs() {
        AgentMetadataBundle first = new DefaultAgentMetadataBootstrap(
                DomainMetadataTestSupport.agentProperties(), documentAssets()).bootstrap();
        AgentMetadataBundle second = new DefaultAgentMetadataBootstrap(
                DomainMetadataTestSupport.agentProperties(), documentAssets()).bootstrap();

        assertThat(first.bundleDigest()).isEqualTo(second.bundleDigest());
    }

    @Test
    void digestChangesWhenEffectiveResourceLimitsChange() {
        var baselineProperties = DomainMetadataTestSupport.agentProperties();
        var changedProperties = DomainMetadataTestSupport.agentProperties();
        changedProperties.getQuery().setMaxSize(baselineProperties.getQuery().getMaxSize() - 1);

        AgentMetadataBundle baseline = new DefaultAgentMetadataBootstrap(
                baselineProperties, documentAssets()).bootstrap();
        AgentMetadataBundle changed = new DefaultAgentMetadataBootstrap(
                changedProperties, documentAssets()).bootstrap();

        assertThat(changed.bundleDigest()).isNotEqualTo(baseline.bundleDigest());
    }

    private static DocumentProfileAssets.BuiltAssets documentAssets() {
        DocumentProfileProperties properties = new DocumentProfileProperties();
        properties.setOwnerAgentId("agent-default");
        properties.setOwnerProfileVersion("profile-v1");
        properties.setPolicyVersion("policy-v1");
        DocumentProfileProperties.Entry entry = new DocumentProfileProperties.Entry();
        entry.setProfileName("employee-document-v1");
        entry.setDomain("employee");
        entry.setDefaultProfile(true);
        entry.setAllowedMaterialTypes(List.of("employee"));
        entry.setAllowedOperations(List.of("SEARCH", "ANSWER", "SUMMARIZE"));
        entry.setAllowedChannels(List.of("BM25"));
        entry.setRequiredChannels(List.of("BM25"));
        entry.setGenerationPolicy(Map.of("SEARCH", DocumentFeaturePolicy.DISABLED,
                "ANSWER", DocumentFeaturePolicy.OPTIONAL, "SUMMARIZE", DocumentFeaturePolicy.OPTIONAL));
        properties.setDefinitions(List.of(entry));
        DocumentProfileProperties.PolicyEntry policy = new DocumentProfileProperties.PolicyEntry();
        policy.setDomain("employee");
        policy.setAllowedProfileNames(List.of("employee-document-v1"));
        policy.setAllowedChannels(List.of("BM25"));
        policy.setAllowedOperations(List.of("SEARCH", "ANSWER", "SUMMARIZE"));
        properties.setPolicy(List.of(policy));
        return DocumentProfileAssets.build(properties);
    }

}
