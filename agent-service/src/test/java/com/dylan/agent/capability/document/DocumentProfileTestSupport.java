package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import com.dylan.agent.capability.document.profile.DocumentProfileProperties;
import com.dylan.agent.capability.document.profile.DocumentProfileSelection;
import com.dylan.agent.capability.document.profile.DocumentProfileSelectionCommand;
import com.dylan.agent.capability.document.profile.DocumentRetrievalProfileResolver;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.List;
import java.util.Map;

final class DocumentProfileTestSupport {
    private DocumentProfileTestSupport() {}

    static DocumentProfileProperties properties() {
        DocumentProfileProperties properties = new DocumentProfileProperties();
        properties.setOwnerAgentId("agent-default");
        properties.setOwnerProfileVersion("profile-v1");
        properties.setPolicyVersion("policy-v1");
        properties.setDefinitions(List.of(entry("tax-policy-v3", true)));
        DocumentProfileProperties.PolicyEntry policy = new DocumentProfileProperties.PolicyEntry();
        policy.setDomain("policy_document");
        policy.setAllowedProfileNames(List.of("tax-policy-v3"));
        policy.setAllowedChannels(List.of("BM25", "DENSE_VECTOR"));
        policy.setAllowedOperations(List.of("SEARCH", "ANSWER", "SUMMARIZE"));
        properties.setPolicy(List.of(policy));
        return properties;
    }

    static DocumentProfileProperties.Entry entry(String name, boolean defaultProfile) {
        DocumentProfileProperties.Entry entry = new DocumentProfileProperties.Entry();
        entry.setProfileName(name);
        entry.setDomain("policy_document");
        entry.setDefaultProfile(defaultProfile);
        entry.setAllowedMaterialTypes(List.of("policy_document"));
        entry.setAllowedOperations(List.of("SEARCH", "ANSWER", "SUMMARIZE"));
        entry.setAllowedChannels(List.of("BM25", "DENSE_VECTOR"));
        entry.setRequiredChannels(List.of("BM25"));
        entry.setChannelWeights(Map.of("BM25", 1, "DENSE_VECTOR", 1));
        entry.setEmbeddingPolicy(DocumentFeaturePolicy.OPTIONAL);
        entry.setRewritePolicy(DocumentFeaturePolicy.OPTIONAL);
        entry.setRerankPolicy(DocumentFeaturePolicy.OPTIONAL);
        entry.setGenerationPolicy(Map.of(
                "SEARCH", DocumentFeaturePolicy.DISABLED,
                "ANSWER", DocumentFeaturePolicy.OPTIONAL,
                "SUMMARIZE", DocumentFeaturePolicy.OPTIONAL));
        return entry;
    }

    static DocumentProfileAssets.BuiltAssets assets() {
        return DocumentProfileAssets.build(properties());
    }

    static AgentProfileRef owner() { return AgentProfileRef.of("agent-default", "profile-v1"); }

    static DocumentProfileSelection selection(DocumentProfileAssets.BuiltAssets assets, DocumentPlanOperation operation) {
        PlanningAuthorizationEvidence evidence = org.mockito.Mockito.mock(PlanningAuthorizationEvidence.class);
        org.mockito.Mockito.when(evidence.agentProfileRef()).thenReturn(owner());
        org.mockito.Mockito.when(evidence.policyVersion()).thenReturn("policy-v1");
        String capabilityId = switch (operation) {
            case SEARCH -> DocumentCapabilityIds.SEARCH;
            case ANSWER -> DocumentCapabilityIds.ANSWER;
            case SUMMARIZE -> DocumentCapabilityIds.SUMMARIZE;
        };
        return new DocumentRetrievalProfileResolver(assets.profileRegistry(), assets.policyRegistry()).select(
                new DocumentProfileSelectionCommand(
                        capabilityId, "policy_document", operation, owner(), "policy-v1", evidence,
                        assets.assetRef().toString(), assets.policyConstraint().evidenceRef(), null, null));
    }

    static DocumentResourceLimit limits(int embeddingTexts, int rerankCandidates, int generatedChars) {
        return new DocumentResourceLimit(
                new DocumentResourceLimit.DocumentInputLimit(1_000, 20),
                new DocumentResourceLimit.DocumentRetrievalLimit(2, 100, 100, 10, 20),
                new DocumentResourceLimit.DocumentEnhancementLimit(10, embeddingTexts,
                        embeddingTexts == 0 ? 0 : 1_536, rerankCandidates),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(20, 20_000, 2_000, 20_000,
                        20, generatedChars, 2_000, 10, 1_000_000));
    }
}
