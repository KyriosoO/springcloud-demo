package com.dylan.esquery.document.search;

import com.fasterxml.jackson.databind.JsonNode;
import com.dylan.esquery.api.model.DocumentSearchChannel;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 在 RRF/dedup 前把 raw ES hit 收敛为 schema-v3 ACL-bound hit。 */
public final class DocumentChannelHitBindingValidator {
    private static final Set<String> REQUIRED_TEXT = Set.of(
            "documentId", "documentVersion", "chunkId", "aclRef", "aclVersion", "tenantId", "status");
    private static final Set<String> SAFE_SOURCE_FIELDS = Set.of(
            "documentId", "documentVersion", "chunkId", "chunkIndex", "aclRef", "aclVersion", "tenantId", "status",
            "title", "sourceType", "section", "page", "sourceUri", "snippet", "content", "citationText",
            "generationText", "charStart", "charEnd", "contextBefore", "contextAfter", "hitFields");

    public BoundDocumentChannelHit bind(
            JsonNode hit,
            DocumentSearchChannel channel,
            int rank,
            Set<String> indexedBusinessFields) {
        if (hit == null || !hit.isObject()) throw new IllegalArgumentException("document raw hit is invalid");
        JsonNode source = hit.path("_source");
        if (!source.isObject()) throw new IllegalArgumentException("document raw hit source is missing");
        for (String field : REQUIRED_TEXT) {
            if (!source.path(field).isTextual() || source.path(field).asText().isBlank()) {
                throw new IllegalArgumentException("document raw hit missing " + field);
            }
        }
        if (!"ACTIVE".equals(source.path("status").asText())) {
            throw new IllegalArgumentException("document raw hit status is not active");
        }
        if (!source.path("chunkIndex").isInt() || source.path("chunkIndex").asInt() < 0) {
            throw new IllegalArgumentException("document raw hit chunkIndex is invalid");
        }
        if (source.has("embedding") || source.has("embeddingText") || source.has("aclPredicate")) {
            throw new IllegalArgumentException("document raw hit exposes prohibited field");
        }
        Set<String> allowed = new HashSet<>(SAFE_SOURCE_FIELDS);
        allowed.addAll(indexedBusinessFields == null ? Set.of() : indexedBusinessFields);
        source.fieldNames().forEachRemaining(field -> {
            if (!allowed.contains(field)) throw new IllegalArgumentException("document raw hit exposes unknown field: " + field);
        });
        if (rank <= 0 || channel == null) throw new IllegalArgumentException("document channel/rank invalid");
        JsonNode scoreNode = hit.path("_score");
        if (!scoreNode.isNumber()) throw new IllegalArgumentException("document raw hit score missing");
        BigDecimal score = scoreNode.decimalValue();
        if (score.signum() < 0) throw new IllegalArgumentException("document raw hit score invalid");
        return new BoundDocumentChannelHit(channel, rank, score,
                source.path("documentId").asText(), source.path("documentVersion").asText(),
                source.path("chunkId").asText(), source.path("chunkIndex").asInt(),
                source.path("aclRef").asText(), source.path("aclVersion").asText(),
                nullableText(source,"title"),nullableText(source,"sourceType"),nullableText(source,"section"),
                nullableInt(source,"page"),nullableText(source,"sourceUri"),nullableText(source,"snippet"),
                nullableText(source,"content"),nullableText(source,"citationText"),nullableText(source,"generationText"),
                nullableInt(source,"charStart"),nullableInt(source,"charEnd"),strings(source.path("contextBefore")),
                strings(source.path("contextAfter")));
    }

    private static String nullableText(JsonNode source,String field){JsonNode n=source.path(field);return n.isTextual()?n.asText():null;}
    private static Integer nullableInt(JsonNode source,String field){JsonNode n=source.path(field);return n.isIntegralNumber()?n.asInt():null;}
    private static List<String> strings(JsonNode node){if(!node.isArray())return List.of();List<String> values=new ArrayList<>();node.forEach(v->{if(!v.isTextual())throw new IllegalArgumentException("document context field invalid");values.add(v.asText());});return List.copyOf(values);}
}
