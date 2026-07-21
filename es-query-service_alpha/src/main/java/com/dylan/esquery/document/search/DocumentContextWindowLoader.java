package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.HybridSearchHit;
import com.dylan.esquery.api.model.document.HybridSearchRequest;
import com.dylan.esquery.document.DocumentCorpusDefinition;
import com.dylan.esquery.document.ResolvedIndexTargetRef;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;

import java.io.IOException;
import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 对已选 anchor 发起唯一一次、同 target/filter 的有界相邻 chunk 查询。 */
public final class DocumentContextWindowLoader {
    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final DocumentChannelExecutorRegistry executors;
    private final DocumentChannelHitBindingValidator hitValidator = new DocumentChannelHitBindingValidator();
    private final Clock clock;

    public DocumentContextWindowLoader(
            RestClient restClient,
            ObjectMapper objectMapper,
            DocumentChannelExecutorRegistry executors,
            Clock clock) {
        this.restClient = restClient;
        this.objectMapper = objectMapper;
        this.executors = executors;
        this.clock = clock;
    }

    public DocumentContextWindowLoadResult loadBatch(
            List<HybridSearchHit> selected,
            HybridSearchRequest request,
            ResolvedIndexTargetRef target,
            DocumentCorpusDefinition corpus) throws IOException {
        List<HybridSearchHit> anchors = List.copyOf(selected == null ? List.of() : selected);
        int before = request.context().beforeChunks();
        int after = request.context().afterChunks();
        if (anchors.isEmpty() || (before == 0 && after == 0) || request.context().maxContextChars() == 0) {
            return new DocumentContextWindowLoadResult(anchors, false);
        }
        requireLive(request);
        Math.multiplyExact((long) anchors.size(), Math.addExact(before, after));
        Set<NeighborKey> requested = requestedNeighbors(anchors, before, after);
        if (requested.isEmpty()) return new DocumentContextWindowLoadResult(anchors, false);

        Request es = new Request("POST", "/" + target.physicalIndex() + "/_search");
        es.setEntity(new NStringEntity(objectMapper.writeValueAsString(body(requested, request, corpus)), ContentType.APPLICATION_JSON));
        Response response = restClient.performRequest(es);
        requireLive(request);
        JsonNode rawHits = objectMapper.readTree(response.getEntity().getContent()).path("hits").path("hits");
        if (!rawHits.isArray()) throw new IllegalArgumentException("document context response hits missing");

        Map<NeighborKey, BoundDocumentChannelHit> neighbors = new LinkedHashMap<>();
        int rank = 1;
        for (JsonNode raw : rawHits) {
            BoundDocumentChannelHit hit = hitValidator.bind(raw, DocumentSearchChannel.BM25, rank++, corpus.indexedBusinessFields());
            NeighborKey key = new NeighborKey(hit.documentId(), hit.documentVersion(), hit.chunkIndex());
            if (!requested.contains(key) || neighbors.putIfAbsent(key, hit) != null) {
                throw new IllegalArgumentException("document context returned extra or duplicate neighbor");
            }
        }

        Budget budget = new Budget(request.context().maxContextChars());
        List<HybridSearchHit> expanded = new ArrayList<>(anchors.size());
        for (HybridSearchHit anchor : anchors) {
            List<String> contextBefore = context(anchor, neighbors, -before, -1, budget);
            List<String> contextAfter = context(anchor, neighbors, 1, after, budget);
            expanded.add(withContext(anchor, contextBefore, contextAfter));
        }
        requireLive(request);
        return new DocumentContextWindowLoadResult(expanded, budget.truncated);
    }

    private Map<String, Object> body(
            Set<NeighborKey> requested,
            HybridSearchRequest request,
            DocumentCorpusDefinition corpus) {
        List<Object> exactNeighbors = requested.stream().map(key -> Map.of("bool", Map.of("filter", List.of(
                Map.of("term", Map.of("documentId", key.documentId)),
                Map.of("term", Map.of("documentVersion", key.documentVersion)),
                Map.of("term", Map.of("chunkIndex", key.chunkIndex)))))).map(Object.class::cast).toList();
        List<Object> filters = new ArrayList<>(executors.compileFilters(request, corpus));
        filters.add(Map.of("bool", Map.of("should", exactNeighbors, "minimum_should_match", 1)));
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("_source", Map.of("excludes", List.of("embedding", "embeddingText", "aclPredicate")));
        body.put("track_total_hits", false);
        body.put("size", requested.size());
        body.put("query", Map.of("constant_score", Map.of("filter", Map.of("bool", Map.of("filter", filters)))));
        return body;
    }

    private static Set<NeighborKey> requestedNeighbors(List<HybridSearchHit> anchors, int before, int after) {
        Set<NeighborKey> keys = new LinkedHashSet<>();
        for (HybridSearchHit anchor : anchors) {
            for (int delta = -before; delta <= after; delta++) {
                if (delta == 0) continue;
                int index = anchor.chunkIndex() + delta;
                if (index >= 0) keys.add(new NeighborKey(anchor.documentId(), anchor.documentVersion(), index));
            }
        }
        return Set.copyOf(keys);
    }

    private static List<String> context(
            HybridSearchHit anchor,
            Map<NeighborKey, BoundDocumentChannelHit> neighbors,
            int fromDelta,
            int toDelta,
            Budget budget) {
        List<String> values = new ArrayList<>();
        for (int delta = fromDelta; delta <= toDelta; delta++) {
            BoundDocumentChannelHit neighbor = neighbors.get(new NeighborKey(
                    anchor.documentId(), anchor.documentVersion(), anchor.chunkIndex() + delta));
            if (neighbor == null) continue;
            requireSameBinding(anchor, neighbor);
            String text = text(neighbor);
            if (text == null || text.isBlank()) continue;
            String clipped = budget.take(text);
            if (!clipped.isEmpty()) values.add(clipped);
        }
        return List.copyOf(values);
    }

    private static void requireSameBinding(HybridSearchHit anchor, BoundDocumentChannelHit neighbor) {
        if (!anchor.documentId().equals(neighbor.documentId())
                || !anchor.documentVersion().equals(neighbor.documentVersion())
                || !anchor.aclRef().equals(neighbor.aclRef())
                || !anchor.aclVersion().equals(neighbor.aclVersion())) {
            throw new IllegalArgumentException("document context neighbor binding mismatch");
        }
    }

    private static String text(BoundDocumentChannelHit hit) {
        if (hit.generationText() != null && !hit.generationText().isBlank()) return hit.generationText();
        if (hit.content() != null && !hit.content().isBlank()) return hit.content();
        if (hit.citationText() != null && !hit.citationText().isBlank()) return hit.citationText();
        return hit.snippet();
    }

    private static HybridSearchHit withContext(HybridSearchHit hit, List<String> before, List<String> after) {
        return new HybridSearchHit(hit.candidateId(), hit.documentId(), hit.documentVersion(), hit.chunkId(), hit.chunkIndex(),
                hit.aclRef(), hit.aclVersion(), hit.title(), hit.sourceType(), hit.section(), hit.page(), hit.sourceUri(),
                hit.snippet(), hit.content(), hit.citationText(), hit.generationText(), before, after, hit.charStart(),
                hit.charEnd(), hit.score(), hit.rrfScore(), hit.channelRanks());
    }

    private void requireLive(HybridSearchRequest request) {
        if (!Instant.ofEpochMilli(request.operationMetadata().absoluteDeadlineEpochMilli()).isAfter(clock.instant())) {
            throw new IllegalStateException("document context deadline exceeded");
        }
    }

    private record NeighborKey(String documentId, String documentVersion, int chunkIndex) {
    }

    private static final class Budget {
        private int remaining;
        private boolean truncated;

        private Budget(int remaining) {
            this.remaining = remaining;
        }

        private String take(String value) {
            int count = value.codePointCount(0, value.length());
            if (remaining <= 0) {
                truncated = true;
                return "";
            }
            if (count <= remaining) {
                remaining -= count;
                return value;
            }
            int end = value.offsetByCodePoints(0, remaining);
            remaining = 0;
            truncated = true;
            return value.substring(0, end);
        }
    }
}
