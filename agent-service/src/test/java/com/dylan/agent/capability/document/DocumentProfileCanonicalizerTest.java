package com.dylan.agent.capability.document;

import com.dylan.agent.capability.document.profile.DocumentProfileAssets;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProfileCanonicalizerTest {
    @Test
    void collectionAndMapOrderDoNotChangeFullDigest() {
        var first = DocumentProfileTestSupport.properties();
        var second = DocumentProfileTestSupport.properties();
        second.getDefinitions().get(0).setAllowedMaterialTypes(List.of("z_notice", "policy_document"));
        first.getDefinitions().get(0).setAllowedMaterialTypes(List.of("policy_document", "z_notice"));
        second.getDefinitions().get(0).setAllowedChannels(List.of("DENSE_VECTOR", "BM25"));
        second.getDefinitions().get(0).setRequiredChannels(List.of("BM25"));
        var reversedWeights = new LinkedHashMap<String, Integer>();
        reversedWeights.put("DENSE_VECTOR", 1);
        reversedWeights.put("BM25", 1);
        second.getDefinitions().get(0).setChannelWeights(reversedWeights);

        var firstAsset = DocumentProfileAssets.build(first).assetRef();
        var secondAsset = DocumentProfileAssets.build(second).assetRef();

        assertThat(firstAsset.assetDigest()).isEqualTo(secondAsset.assetDigest()).hasSize(64);
        assertThat(firstAsset.documentProfileVersion()).isEqualTo("dp1-" + firstAsset.assetDigest());
    }

    @Test
    void semanticFieldChangeChangesDigest() {
        var first = DocumentProfileTestSupport.properties();
        var second = DocumentProfileTestSupport.properties();
        second.getDefinitions().get(0).setRrfK(61);

        assertThat(DocumentProfileAssets.build(first).assetRef().assetDigest())
                .isNotEqualTo(DocumentProfileAssets.build(second).assetRef().assetDigest());
    }

    @Test
    void duplicateDefaultRejectsWholeCandidate() {
        var properties = DocumentProfileTestSupport.properties();
        properties.setDefinitions(List.of(
                DocumentProfileTestSupport.entry("tax-policy-v3", true),
                DocumentProfileTestSupport.entry("tax-policy-secondary", true)));
        properties.getPolicy().get(0).setAllowedProfileNames(List.of("tax-policy-v3", "tax-policy-secondary"));

        assertThatThrownBy(() -> DocumentProfileAssets.build(properties))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("exactly one default");
    }
}
