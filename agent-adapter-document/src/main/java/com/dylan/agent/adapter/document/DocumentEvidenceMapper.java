package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.AdapterDocumentRetrievalDiagnostics;
import com.dylan.esquery.api.model.HybridRetrievalDiagnostics;
import com.dylan.esquery.api.model.HybridSearchHit;
import com.dylan.esquery.api.model.HybridSearchResponse;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class DocumentEvidenceMapper {

    private static final String EMBEDDING_FIELD = "embedding";

    private final ObjectMapper objectMapper;
    private final DocumentAdapterProperties properties;

    public DocumentEvidenceMapper(ObjectMapper objectMapper, DocumentAdapterProperties properties) {
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper must not be null");
        this.properties = Objects.requireNonNull(properties, "properties must not be null");
    }

    public AdapterDocumentResult toAdapterResult(String responseBody, int requestedCount) {
        try {
            JsonNode root = objectMapper.readTree(responseBody);
            List<AdapterDocumentEvidence> evidence = hits(root);
            AdapterDocumentResult result = new AdapterDocumentResult();
            result.setHits(evidence);
            result.setCitations(evidence);
            result.setRequestedDocumentCount(requestedCount);
            result.setCoveredDocumentCount((int) evidence.stream()
                    .map(AdapterDocumentEvidence::getDocumentId)
                    .filter(Objects::nonNull)
                    .distinct()
                    .count());
            return result;
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to parse document search response", ex);
        }
    }

    public AdapterDocumentResult toAdapterResult(HybridSearchResponse response, int requestedCount) {
        HybridSearchResponse safe = response == null ? new HybridSearchResponse() : response;
        List<AdapterDocumentEvidence> evidence = safe.getHits() == null ? List.of() : safe.getHits().stream()
                .map(this::toEvidence)
                .toList();
        AdapterDocumentResult result = new AdapterDocumentResult();
        result.setHits(evidence);
        result.setCitations(evidence);
        result.setRequestedDocumentCount(requestedCount);
        result.setCoveredDocumentCount((int) evidence.stream()
                .map(AdapterDocumentEvidence::getDocumentId)
                .filter(Objects::nonNull)
                .distinct()
                .count());
        result.setPartial(safe.isPartial());
        result.setRetrievalDiagnostics(toDiagnostics(safe.getDiagnostics(), "HYBRID"));
        return result;
    }

    private List<AdapterDocumentEvidence> hits(JsonNode root) {
        JsonNode hitsNode = root.path("hits").path("hits");
        if (!hitsNode.isArray()) {
            return List.of();
        }
        List<AdapterDocumentEvidence> evidence = new ArrayList<>();
        Iterator<JsonNode> iterator = hitsNode.elements();
        while (iterator.hasNext()) {
            evidence.add(toEvidence(iterator.next()));
        }
        return evidence;
    }

    private AdapterDocumentEvidence toEvidence(JsonNode hit) {
        JsonNode source = hit.path("_source");
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId(text(source, "documentId", text(hit, "_id", null)));
        evidence.setChunkId(text(source, "chunkId", evidence.getDocumentId()));
        evidence.setTitle(text(source, properties.getDefaultTitleField(), null));
        evidence.setSourceType(text(source, properties.getSourceTypeField(), null));
        evidence.setSection(text(source, properties.getSectionField(), null));
        evidence.setPage(integer(source, properties.getPageField()));
        evidence.setSourceUri(text(source, properties.getSourceUriField(), null));
        evidence.setSnippet(text(source, "snippet", text(source, properties.getDefaultSnippetField(), null)));
        evidence.setContent(text(source, "content", null));
        evidence.setChunkIndex(integer(source, "chunkIndex"));
        evidence.setCharStart(integer(source, "charStart"));
        evidence.setCharEnd(integer(source, "charEnd"));
        evidence.setScore(score(hit));
        if (source.isObject()) {
            @SuppressWarnings("unchecked")
            Map<String, Object> metadata = objectMapper.convertValue(source, Map.class);
            evidence.setMetadata(sanitizeMetadata(metadata));
        }
        return evidence;
    }

    private AdapterDocumentEvidence toEvidence(HybridSearchHit hit) {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId(hit.getDocumentId());
        evidence.setChunkId(hit.getChunkId());
        evidence.setTitle(hit.getTitle());
        evidence.setSourceType(hit.getSourceType());
        evidence.setSection(hit.getSection());
        evidence.setPage(hit.getPage());
        evidence.setSourceUri(hit.getSourceUri());
        evidence.setSnippet(hit.getSnippet());
        evidence.setContent(hit.getContent());
        evidence.setContextBefore(hit.getContextBefore());
        evidence.setContextAfter(hit.getContextAfter());
        evidence.setChunkIndex(hit.getChunkIndex());
        evidence.setCharStart(hit.getCharStart());
        evidence.setCharEnd(hit.getCharEnd());
        evidence.setKeywordRank(hit.getKeywordRank());
        evidence.setVectorRank(hit.getVectorRank());
        evidence.setRrfScore(hit.getRrfScore());
        evidence.setRetrievalChannels(hit.getRetrievalChannels());
        evidence.setScore(hit.getScore());
        evidence.setMetadata(enrichMetadata(hit));
        return evidence;
    }

    private Map<String, Object> enrichMetadata(HybridSearchHit hit) {
        Map<String, Object> metadata = sanitizeMetadata(hit.getMetadata());
        Map<String, Object> enriched = metadata == null ? new LinkedHashMap<>() : new LinkedHashMap<>(metadata);
        if (hit.getChannelRanks() != null && !hit.getChannelRanks().isEmpty()) {
            enriched.put("channelRanks", hit.getChannelRanks());
        }
        if (hit.getChannelScores() != null && !hit.getChannelScores().isEmpty()) {
            enriched.put("channelScores", hit.getChannelScores());
        }
        if (hit.getHitFields() != null && !hit.getHitFields().isEmpty()) {
            enriched.put("hitFields", hit.getHitFields());
        }
        if (hit.getDedupGroupSize() != null) {
            enriched.put("dedupGroupSize", hit.getDedupGroupSize());
        }
        if (hit.getRepresentativeChunk() != null) {
            enriched.put("representativeChunk", hit.getRepresentativeChunk());
        }
        if (hit.getRerankScore() != null) {
            enriched.put("rerankScore", hit.getRerankScore());
        }
        if (hit.getRerankReasonCode() != null) {
            enriched.put("rerankReasonCode", hit.getRerankReasonCode());
        }
        return enriched.isEmpty() ? metadata : enriched;
    }

    private static Map<String, Object> sanitizeMetadata(Map<String, Object> metadata) {
        if (metadata == null || metadata.isEmpty()) {
            return metadata;
        }
        Map<String, Object> sanitized = new LinkedHashMap<>(metadata);
        sanitized.remove(EMBEDDING_FIELD);
        return sanitized;
    }

    private AdapterDocumentRetrievalDiagnostics toDiagnostics(HybridRetrievalDiagnostics source, String mode) {
        AdapterDocumentRetrievalDiagnostics target = new AdapterDocumentRetrievalDiagnostics();
        target.setRetrievalMode(mode);
        if (source != null) {
            target.setKeywordHitCount(source.getKeywordHitCount());
            target.setVectorHitCount(source.getVectorHitCount());
            target.setReturnedHitCount(source.getReturnedHitCount());
            target.setFusedCandidateCount(source.getFusedCandidateCount());
            target.setDedupedCandidateCount(source.getDedupedCandidateCount());
            target.setRrfK(source.getRrfK());
            target.setMaxChunksPerDocument(source.getMaxChunksPerDocument());
            target.setChannelHitCounts(source.getChannelHitCounts());
            target.setChannelWeights(source.getChannelWeights());
            target.setFusionStrategy(source.getFusionStrategy());
            target.setRerankStatus(source.getRerankStatus());
            target.setRerankSkippedReason(source.getRerankSkippedReason());
            target.setDegraded(Boolean.TRUE.equals(source.getDegraded()));
            target.setDegradationReason(source.getDegradationReason());
        }
        return target;
    }

    private static BigDecimal score(JsonNode hit) {
        JsonNode score = hit.path("_score");
        return score.isNumber() ? score.decimalValue() : null;
    }

    private static Integer integer(JsonNode source, String field) {
        JsonNode value = source.path(field);
        return value.isInt() ? value.asInt() : null;
    }

    private static String text(JsonNode source, String field, String fallback) {
        JsonNode value = source.path(field);
        if (value.isMissingNode() || value.isNull()) {
            return fallback;
        }
        return value.asText();
    }
}
