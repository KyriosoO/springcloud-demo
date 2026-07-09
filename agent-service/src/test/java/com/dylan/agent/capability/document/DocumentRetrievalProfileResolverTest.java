package com.dylan.agent.capability.document;

import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentRetrievalProfileResolverTest {

    @Test
    void resolvesDomainMaterialTypeProfile() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        AgentProperties.RetrievalProfileProperties profile = profile(
                "policy_document",
                List.of("policy", "notice"),
                "tax-policy-default",
                "agent-doc-tax-policy-read");
        profile.setChannels(List.of("bm25", "exact", "dense_vector"));
        profile.setChannelWeights(Map.of("bm25", 1.5d));
        profile.setEmbeddingField("embedding_v2");
        profile.setEmbeddingProvider("bge");
        profile.setEmbeddingModel("bge-large-zh-v2");
        profile.setEmbeddingDimension(1024);
        properties.getDocument().getRetrievalProfiles().put("tax-policy-default", profile);

        DocumentRetrievalProfile resolved = new DocumentRetrievalProfileResolver(properties)
                .resolve("policy_document", "notice", null);

        assertThat(resolved.domain()).isEqualTo("policy_document");
        assertThat(resolved.materialType()).isEqualTo("notice");
        assertThat(resolved.retrievalProfile()).isEqualTo("tax-policy-default");
        assertThat(resolved.profileVersion()).startsWith("pv-");
        assertThat(resolved.indexAlias()).isEqualTo("agent-doc-tax-policy-read");
        assertThat(resolved.hybridOptions().channels()).containsExactly("BM25", "EXACT", "DENSE_VECTOR");
        assertThat(resolved.hybridOptions().channelWeights()).containsEntry("BM25", 1.5d);
        assertThat(resolved.hybridOptions().embeddingField()).isEqualTo("embedding_v2");
        assertThat(resolved.hybridOptions().embeddingProvider()).isEqualTo("bge");
        assertThat(resolved.hybridOptions().embeddingModel()).isEqualTo("bge-large-zh-v2");
        assertThat(resolved.hybridOptions().embeddingDimension()).isEqualTo(1024);
    }

    @Test
    void rejectsProfileOutsideDomain() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRetrievalProfiles().put("tax-policy-default", profile(
                "policy_document",
                List.of("policy"),
                "tax-policy-default",
                "agent-doc-tax-policy-read"));

        assertThatThrownBy(() -> new DocumentRetrievalProfileResolver(properties)
                .resolve("law_document", "policy", "tax-policy-default"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retrievalProfile");
    }

    @Test
    void rejectsMaterialTypeOutsideProfile() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRetrievalProfiles().put("tax-policy-default", profile(
                "policy_document",
                List.of("policy"),
                "tax-policy-default",
                "agent-doc-tax-policy-read"));

        assertThatThrownBy(() -> new DocumentRetrievalProfileResolver(properties)
                .resolve("policy_document", "faq", "tax-policy-default"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("materialType");
    }

    @Test
    void derivesNewVersionWhenProfileContentChanges() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        AgentProperties.RetrievalProfileProperties profile = profile(
                "policy_document",
                List.of("policy"),
                "tax-policy-default",
                "agent-doc-tax-policy-read");
        properties.getDocument().getRetrievalProfiles().put("tax-policy-default", profile);
        DocumentRetrievalProfileResolver resolver = new DocumentRetrievalProfileResolver(properties);

        String firstVersion = resolver.resolve("policy_document", "policy", null).profileVersion();
        profile.setIndexAlias("agent-doc-tax-policy-read-v2");
        String secondVersion = resolver.resolve("policy_document", "policy", null).profileVersion();

        assertThat(secondVersion).startsWith("pv-");
        assertThat(secondVersion).isNotEqualTo(firstVersion);
    }

    @Test
    void rejectsMissingDomainProfileWithoutLegacyFallback() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();

        assertThatThrownBy(() -> new DocumentRetrievalProfileResolver(properties)
                .resolve("policy_document", null, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("retrievalProfile");
    }

    @Test
    void rejectsAmbiguousDomainProfilesWhenMaterialTypeIsMissing() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRetrievalProfiles().put("policy-default", profile(
                "policy_document",
                List.of("policy"),
                "policy-default",
                "agent-doc-policy-read"));
        properties.getDocument().getRetrievalProfiles().put("tax-v2", profile(
                "policy_document",
                List.of("tax_policy"),
                "tax-v2",
                "agent-doc-tax-policy-read"));

        assertThatThrownBy(() -> new DocumentRetrievalProfileResolver(properties)
                .resolve("policy_document", null, null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("materialType or retrievalProfile");
    }

    @Test
    void resolvesSingleDomainProfileWhenMaterialTypeIsMissing() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRetrievalProfiles().put("policy-default", profile(
                "policy_document",
                List.of("policy"),
                "policy-default",
                "agent-doc-policy-read"));

        DocumentRetrievalProfile resolved = new DocumentRetrievalProfileResolver(properties)
                .resolve("policy_document", null, null);

        assertThat(resolved.materialType()).isEqualTo("policy");
        assertThat(resolved.retrievalProfile()).isEqualTo("policy-default");
    }

    @Test
    void rejectsProfileWithoutExplicitChannels() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        AgentProperties.RetrievalProfileProperties profile = profile(
                "policy_document",
                List.of("policy"),
                "policy-default",
                "agent-doc-policy-read");
        profile.setChannels(List.of());
        properties.getDocument().getRetrievalProfiles().put("policy-default", profile);

        assertThatThrownBy(() -> new DocumentRetrievalProfileResolver(properties)
                .resolve("policy_document", "policy", null))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("channels");
    }

    private AgentProperties.RetrievalProfileProperties profile(
            String domain,
            List<String> materialTypes,
            String retrievalProfile,
            String indexAlias) {
        AgentProperties.RetrievalProfileProperties profile = new AgentProperties.RetrievalProfileProperties();
        profile.setDomain(domain);
        profile.setMaterialTypes(materialTypes);
        profile.setRetrievalProfile(retrievalProfile);
        profile.setIndexAlias(indexAlias);
        return profile;
    }
}
