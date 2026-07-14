package com.dylan.agent.capability.document;

import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import com.dylan.agent.capability.document.profile.DocumentProfileSelectionCommand;
import com.dylan.agent.capability.document.profile.DocumentRetrievalProfileResolver;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentRetrievalProfileResolverTest {
    @Test
    void selectsDefaultFromExactAssetAndPolicyEvidence() {
        DocumentProfileAssets.BuiltAssets assets = DocumentProfileTestSupport.assets();
        var resolver = new DocumentRetrievalProfileResolver(assets.profileRegistry(), assets.policyRegistry());
        var selection = resolver.select(command(assets, null, "policy_document"));

        assertThat(selection.selectedProfileName()).isEqualTo("tax-policy-v3");
        assertThat(selection.assetRef().documentProfileVersion()).matches("dp1-[0-9a-f]{64}");
        assertThat(selection.allowedCorpora()).hasSize(1);
        assertThat(selection.selectionDigest()).hasSize(64);
    }

    @Test
    void explicitUnknownProfileNeverFallsBackToDefault() {
        DocumentProfileAssets.BuiltAssets assets = DocumentProfileTestSupport.assets();
        var resolver = new DocumentRetrievalProfileResolver(assets.profileRegistry(), assets.policyRegistry());

        assertThatThrownBy(() -> resolver.select(command(assets, "unknown-profile", null)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("not allowed");
    }

    @Test
    void rejectsContributionThatDoesNotBindExactChildAsset() {
        DocumentProfileAssets.BuiltAssets assets = DocumentProfileTestSupport.assets();
        var resolver = new DocumentRetrievalProfileResolver(assets.profileRegistry(), assets.policyRegistry());
        DocumentProfileSelectionCommand command = command(assets, null, null);
        command = new DocumentProfileSelectionCommand(command.capabilityId(), command.domain(), command.operation(),
                command.agentProfileRef(), command.policyVersion(), command.authorizationEvidence(),
                "wrong-ref", command.policyContributionEvidenceRef(), null, null);

        DocumentProfileSelectionCommand invalid = command;
        assertThatThrownBy(() -> resolver.select(invalid))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("exact child asset");
    }

    private static DocumentProfileSelectionCommand command(
            DocumentProfileAssets.BuiltAssets assets,
            String requestedProfile,
            String materialType) {
        PlanningAuthorizationEvidence evidence = mock(PlanningAuthorizationEvidence.class);
        when(evidence.agentProfileRef()).thenReturn(DocumentProfileTestSupport.owner());
        when(evidence.policyVersion()).thenReturn("policy-v1");
        return new DocumentProfileSelectionCommand(
                DocumentCapabilityIds.SEARCH, "policy_document", DocumentPlanOperation.SEARCH,
                DocumentProfileTestSupport.owner(), "policy-v1", evidence,
                assets.assetRef().toString(), assets.policyConstraint().evidenceRef(),
                requestedProfile, materialType);
    }
}
