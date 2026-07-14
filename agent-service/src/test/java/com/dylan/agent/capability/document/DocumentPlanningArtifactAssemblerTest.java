package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalChannel;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.profile.DocumentFeaturePolicy;
import com.dylan.agent.capability.document.profile.DocumentPlanningProfileProjector;
import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import com.dylan.agent.capability.document.profile.DocumentProfileProjectionDigest;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentPlanningArtifactAssemblerTest {
    private final DocumentPlanningProfileProjector projector = new DocumentPlanningProfileProjector();

    @Test
    void optionalZeroBudgetsRemoveVectorAndRerankFromFrozenProjection() {
        var projected = projector.project(selection(), DocumentProfileTestSupport.limits(0, 0, 0),
                DocumentCapabilityIds.SEARCH);

        assertThat(projected.embeddingPolicy()).isEqualTo(DocumentFeaturePolicy.DISABLED);
        assertThat(projected.rerankPolicy()).isEqualTo(DocumentFeaturePolicy.DISABLED);
        assertThat(projected.allowedChannels()).containsExactly(DocumentRetrievalChannel.BM25);
        assertThat(projected.requiredChannels()).containsExactly(DocumentRetrievalChannel.BM25);
    }

    @Test
    void requiredFeatureWithZeroBudgetFailsBeforeRuntimePlanAssembly() {
        var properties = DocumentProfileTestSupport.properties();
        properties.getDefinitions().get(0).setEmbeddingPolicy(DocumentFeaturePolicy.REQUIRED);
        properties.getDefinitions().get(0).setRequiredChannels(
                List.of(DocumentRetrievalChannel.BM25.name(), DocumentRetrievalChannel.DENSE_VECTOR.name()));
        DocumentProfileAssets.BuiltAssets assets = DocumentProfileAssets.build(properties);

        assertThatThrownBy(() -> projector.project(selection(assets),
                DocumentProfileTestSupport.limits(0, 10, 0), DocumentCapabilityIds.SEARCH))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("required document embedding");
    }

    @Test
    void profileProjectionDigestChangesWhenEffectiveGateChangesProjection() {
        var unrestricted = projector.project(selection(), DocumentProfileTestSupport.limits(10, 20, 10),
                DocumentCapabilityIds.SEARCH);
        var gated = projector.project(selection(), DocumentProfileTestSupport.limits(0, 0, 0),
                DocumentCapabilityIds.SEARCH);

        assertThat(DocumentProfileProjectionDigest.compute(gated))
                .isNotEqualTo(DocumentProfileProjectionDigest.compute(unrestricted));
    }

    private static com.dylan.agent.capability.document.profile.DocumentProfileSelection selection() {
        return selection(DocumentProfileTestSupport.assets());
    }

    private static com.dylan.agent.capability.document.profile.DocumentProfileSelection selection(
            DocumentProfileAssets.BuiltAssets assets) {
        return DocumentProfileTestSupport.selection(assets, DocumentPlanOperation.SEARCH);
    }
}
