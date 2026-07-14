package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.DocumentHybridChannelRequest;
import com.dylan.esquery.api.model.document.HybridContextRequest;
import com.dylan.esquery.api.model.document.HybridDedupRequest;
import com.dylan.esquery.api.model.document.HybridFusionRequest;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentRrfMergerTest {
    private final DocumentRrfMerger merger = new DocumentRrfMerger();

    @Test
    void producesStableWeightedRrfOrderIndependentOfMapInsertionOrder() {
        var request = request();
        var bm25 = List.of(hit(DocumentSearchChannel.BM25, "c-1", 0, "2.0"),
                hit(DocumentSearchChannel.BM25, "c-2", 1, "1.0"));
        var dense = List.of(hit(DocumentSearchChannel.DENSE_VECTOR, "c-2", 1, "3.0"),
                hit(DocumentSearchChannel.DENSE_VECTOR, "c-1", 0, "1.0"));
        Map<DocumentSearchChannel, List<BoundDocumentChannelHit>> first = new EnumMap<>(DocumentSearchChannel.class);
        first.put(DocumentSearchChannel.BM25, bm25);
        first.put(DocumentSearchChannel.DENSE_VECTOR, dense);
        Map<DocumentSearchChannel, List<BoundDocumentChannelHit>> second = new java.util.LinkedHashMap<>();
        second.put(DocumentSearchChannel.DENSE_VECTOR, dense);
        second.put(DocumentSearchChannel.BM25, bm25);

        var firstResult = merger.merge(first, request);
        var secondResult = merger.merge(second, request);

        assertThat(firstResult).extracting(item -> item.representative().chunkId()).containsExactly("c-2", "c-1");
        assertThat(secondResult).extracting(item -> item.representative().chunkId()).containsExactly("c-2", "c-1");
        assertThat(firstResult).extracting(FusedDocumentHit::rrfScore)
                .containsExactlyElementsOf(secondResult.stream().map(FusedDocumentHit::rrfScore).toList());
    }

    @Test
    void rejectsSameChunkWithDifferentSecurityBinding() {
        BoundDocumentChannelHit changed = new BoundDocumentChannelHit(
                DocumentSearchChannel.DENSE_VECTOR, 1, BigDecimal.ONE, "doc-1", "v1", "c-1", 0,
                "acl-other", "v1", "title", "policy", null, null, null, "text", "content", null,
                null, null, null, List.of(), List.of());

        assertThatThrownBy(() -> merger.merge(Map.of(
                DocumentSearchChannel.BM25, List.of(hit(DocumentSearchChannel.BM25, "c-1", 0, "1.0")),
                DocumentSearchChannel.DENSE_VECTOR, List.of(changed)), request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("binding mismatch");
    }

    private static com.dylan.esquery.api.model.document.HybridSearchRequest request() {
        return DocumentSearchTestFixtures.request(new HybridContextRequest(0, 0, 0), List.of(
                        new DocumentHybridChannelRequest(DocumentSearchChannel.BM25, true, 1, 10),
                        new DocumentHybridChannelRequest(DocumentSearchChannel.DENSE_VECTOR, false, 2, 10)),
                new HybridFusionRequest(60, 10), new HybridDedupRequest(5, 2));
    }

    private static BoundDocumentChannelHit hit(DocumentSearchChannel channel, String chunkId, int chunkIndex, String score) {
        return new BoundDocumentChannelHit(channel, 1, new BigDecimal(score), "doc-1", "v1", chunkId, chunkIndex,
                "acl-1", "v1", "title", "policy", null, null, null, "text", "content", null,
                null, null, null, List.of(), List.of());
    }
}
