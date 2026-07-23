package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.DocumentChannelRank;
import com.dylan.esquery.api.model.document.HybridContextRequest;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentResultSelectorTest {
    private final DocumentResultSelector selector = new DocumentResultSelector();

    @Test
    void preservesRrfOrderAndEnforcesDistinctDocumentAndChunkLimits() {
        var selected = selector.select(List.of(
                        fused(hit("doc-1", "v1", "c-1", 0, "acl-1"), "0.9"),
                        fused(hit("doc-1", "v1", "c-2", 1, "acl-1"), "0.8"),
                        fused(hit("doc-1", "v1", "c-3", 2, "acl-1"), "0.7"),
                        fused(hit("doc-2", "v1", "c-4", 0, "acl-2"), "0.6")),
                DocumentSearchTestFixtures.request(new HybridContextRequest(0, 0, 0)),
                DocumentSearchTestFixtures.target().binding());

        assertThat(selected).extracting(item -> item.chunkId()).containsExactly("c-1", "c-2", "c-4");
        assertThat(selected).allSatisfy(item -> {
            assertThat(item.contextBefore()).isEmpty();
            assertThat(item.contextAfter()).isEmpty();
            assertThat(item.candidateId()).hasSize(64);
        });
    }

    @Test
    void rejectsSameDocumentIdWithDifferentVersionOrAclBinding() {
        assertThatThrownBy(() -> selector.select(List.of(
                        fused(hit("doc-1", "v1", "c-1", 0, "acl-1"), "0.9"),
                        fused(hit("doc-1", "v2", "c-2", 1, "acl-2"), "0.8")),
                DocumentSearchTestFixtures.request(new HybridContextRequest(0, 0, 0)),
                DocumentSearchTestFixtures.target().binding()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("binding conflict");
    }

    private static BoundDocumentChannelHit hit(
            String documentId, String version, String chunkId, int chunkIndex, String aclRef) {
        return new BoundDocumentChannelHit(DocumentSearchChannel.BM25, 1, BigDecimal.ONE,
                documentId, version, chunkId, chunkIndex, aclRef, "v1", "title", "policy", null,
                null, null, "snippet", "content", null, null, null, null, List.of(), List.of());
    }

    private static FusedDocumentHit fused(BoundDocumentChannelHit hit, String score) {
        return new FusedDocumentHit(hit, new BigDecimal(score), 1,
                List.of(new DocumentChannelRank(DocumentSearchChannel.BM25, 1, BigDecimal.ONE)));
    }
}
