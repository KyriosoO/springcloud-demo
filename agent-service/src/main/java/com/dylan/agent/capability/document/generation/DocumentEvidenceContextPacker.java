package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.api.plan.DocumentPlanOperation;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.HexFormat;
import java.util.stream.Collectors;

/** 将过滤后的 evidence 打包为 LLM 可消费上下文。 */
public class DocumentEvidenceContextPacker {

    public EvidenceContextPackage pack(DocumentContextPackRequest request) {
        DocumentContextBudget budget = request.budget();
        Map<String, DocumentEvidenceContextItem> items = new LinkedHashMap<>();
        int[] usedChars = {0};
        request.evidence().stream()
                .sorted(Comparator
                        .comparing(AdapterDocumentEvidence::getRrfScore, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(AdapterDocumentEvidence::getScore, Comparator.nullsLast(Comparator.reverseOrder()))
                        .thenComparing(AdapterDocumentEvidence::getChunkIndex, Comparator.nullsLast(Integer::compareTo)))
                .forEach(evidence -> {
                    if (items.size() >= budget.maxEvidenceCount()) {
                        return;
                    }
                    String citationId = citationId(evidence);
                    if (items.containsKey(citationId)) {
                        return;
                    }
                    String text = truncate(text(evidence), budget.maxEvidenceChars());
                    if (usedChars[0] + text.length() > budget.maxContextChars()) {
                        return;
                    }
                    usedChars[0] += text.length();
                    items.put(citationId, new DocumentEvidenceContextItem(citationId, text, safeMetadata(evidence)));
                });
        List<DocumentEvidenceContextItem> evidenceItems = List.copyOf(items.values());
        Set<String> citationIds = evidenceItems.stream()
                .map(DocumentEvidenceContextItem::citationId)
                .collect(Collectors.toUnmodifiableSet());
        return new EvidenceContextPackage(
                request.context().invocationId(),
                request.plan().request().getOperation(),
                request.plan().request().getQueryText(),
                evidenceItems,
                citationIds,
                budget,
                digest(evidenceItems));
    }

    private static String citationId(AdapterDocumentEvidence evidence) {
        if (evidence.getChunkId() != null && !evidence.getChunkId().isBlank()) {
            return evidence.getChunkId();
        }
        return evidence.getDocumentId();
    }

    private static String text(AdapterDocumentEvidence evidence) {
        String base = evidence.getContent() == null || evidence.getContent().isBlank()
                ? evidence.getSnippet()
                : evidence.getContent();
        List<String> before = evidence.getContextBefore() == null ? List.of() : evidence.getContextBefore();
        List<String> after = evidence.getContextAfter() == null ? List.of() : evidence.getContextAfter();
        return java.util.stream.Stream.concat(
                        java.util.stream.Stream.concat(before.stream(), java.util.stream.Stream.of(base == null ? "" : base)),
                        after.stream())
                .filter(value -> value != null && !value.isBlank())
                .collect(Collectors.joining("\n"));
    }

    private static Map<String, Object> safeMetadata(AdapterDocumentEvidence evidence) {
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("documentId", evidence.getDocumentId());
        metadata.put("title", evidence.getTitle());
        metadata.put("section", evidence.getSection());
        metadata.put("page", evidence.getPage());
        metadata.put("sourceUri", evidence.getSourceUri());
        metadata.put("chunkIndex", evidence.getChunkIndex());
        return metadata;
    }

    private static String truncate(String value, int limit) {
        if (value == null) {
            return "";
        }
        return value.length() <= limit ? value : value.substring(0, limit);
    }

    private static String digest(List<DocumentEvidenceContextItem> items) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (DocumentEvidenceContextItem item : items) {
                digest.update(item.citationId().getBytes(StandardCharsets.UTF_8));
                digest.update(item.text().getBytes(StandardCharsets.UTF_8));
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 not available", ex);
        }
    }
}
