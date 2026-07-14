package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 不读score、不重排的count/chars/document/chunk稳定前缀选择器。 */
public final class DocumentEvidenceSelector {
    public SelectedDocumentEvidence select(List<AclBoundDocumentHit> ordered,
                                           DocumentResourceLimit limits) {
        int maxCount = Math.min(limits.output().maxEvidenceCount(), limits.output().maxCitationCount());
        if (maxCount <= 0) return new SelectedDocumentEvidence(List.of(), 0, !ordered.isEmpty());
        List<AclBoundDocumentHit> selected = new ArrayList<>();
        Map<String, Integer> chunksPerDocument = new HashMap<>();
        Set<String> documents = new HashSet<>();
        int chars = 0;
        boolean truncated = false;
        for (AclBoundDocumentHit hit : ordered) {
            if (selected.size() >= maxCount) { truncated = true; break; }
            String sourceIdentity = hit.identity().sourceIdentity();
            int chunks = chunksPerDocument.getOrDefault(sourceIdentity, 0);
            if (chunks >= limits.retrieval().maxChunksPerDocument()) { truncated = true; break; }
            if (!documents.contains(sourceIdentity) && documents.size() >= limits.retrieval().maxReturnedDocuments()) {
                truncated = true; break;
            }
            AclBoundDocumentHit bounded = withBoundedSnippet(hit, limits.output().maxSnippetChars());
            int itemChars = evidenceChars(bounded);
            int next;
            try { next = Math.addExact(chars, itemChars); }
            catch (ArithmeticException ex) { truncated = true; break; }
            if (next > limits.output().maxEvidenceChars()) { truncated = true; break; }
            selected.add(bounded); chars = next; documents.add(sourceIdentity);
            chunksPerDocument.put(sourceIdentity, chunks + 1);
        }
        if (selected.size() < ordered.size()) truncated = true;
        return new SelectedDocumentEvidence(selected, chars, truncated);
    }

    private static int evidenceChars(AclBoundDocumentHit hit) {
        int total = 0;
        for (String value : List.of(nullable(hit.title()), nullable(hit.section()), nullable(displaySnippet(hit)))) {
            total = Math.addExact(total, value.codePointCount(0, value.length()));
        }
        return total;
    }
    private static AclBoundDocumentHit withBoundedSnippet(AclBoundDocumentHit hit, int maxChars) {
        String boundedCitation = prefix(hit.citationText(), maxChars);
        String boundedSnippet = prefix(hit.snippet(), maxChars);
        return new AclBoundDocumentHit(hit.candidateId(), hit.identity(), hit.title(), hit.sourceType(), hit.section(),
                hit.page(), hit.sourceUri(), boundedSnippet, hit.content(), boundedCitation, hit.generationText(),
                hit.contextBefore(), hit.contextAfter(), hit.charStart(), hit.charEnd(), hit.score(), hit.rrfScore(),
                hit.retrievalChannels(), hit.safeFieldNames(), hit.securityBinding());
    }
    private static String prefix(String value, int maxChars) {
        if (value == null || value.isBlank()) return value;
        int count = value.codePointCount(0, value.length());
        if (count <= maxChars) return value;
        return value.substring(0, value.offsetByCodePoints(0, maxChars));
    }
    private static String displaySnippet(AclBoundDocumentHit hit) { return hit.citationText() == null || hit.citationText().isBlank() ? hit.snippet() : hit.citationText(); }
    private static String nullable(String value) { return value == null ? "" : value; }
}
