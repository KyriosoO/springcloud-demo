package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Objects;
import java.util.Set;

/** LLM 输入前的最小安全过滤。 */
public class DocumentEvidencePreSecurityFilter {

    private static final String CONTENT_FIELD = "content";
    private static final String SNIPPET_FIELD = "snippet";
    private static final String TITLE_FIELD = "title";
    private static final String SOURCE_TYPE_FIELD = "sourceType";
    private static final String SECTION_FIELD = "section";
    private static final String PAGE_FIELD = "page";
    private static final String SOURCE_URI_FIELD = "sourceUri";

    public List<AdapterDocumentEvidence> filter(
            List<AdapterDocumentEvidence> evidence,
            ExecutionScope scope,
            String domain) {
        Set<String> allowedFields = allowedFields(scope, domain);
        if (scope != null && (!scope.allowedDomains().contains(domain)
                || !hasReadableEvidenceText(allowedFields))) {
            return List.of();
        }
        return (evidence == null ? List.<AdapterDocumentEvidence>of() : evidence).stream()
                .filter(Objects::nonNull)
                .filter(item -> citationId(item) != null)
                .map(item -> sanitize(item, allowedFields))
                .filter(item -> text(item) != null && !text(item).isBlank())
                .toList();
    }

    private static Set<String> allowedFields(ExecutionScope scope, String domain) {
        if (scope == null) {
            return Set.of(CONTENT_FIELD, SNIPPET_FIELD, TITLE_FIELD, SOURCE_TYPE_FIELD,
                    SECTION_FIELD, PAGE_FIELD, SOURCE_URI_FIELD);
        }
        return scope.allowedFields().getOrDefault(domain, Set.of());
    }

    private static boolean hasReadableEvidenceText(Set<String> allowedFields) {
        return allowedFields.contains(CONTENT_FIELD) || allowedFields.contains(SNIPPET_FIELD);
    }

    private static AdapterDocumentEvidence sanitize(AdapterDocumentEvidence source, Set<String> allowedFields) {
        AdapterDocumentEvidence target = new AdapterDocumentEvidence();
        target.setDocumentId(source.getDocumentId());
        target.setChunkId(source.getChunkId());
        target.setTitle(allowedFields.contains(TITLE_FIELD) ? source.getTitle() : null);
        target.setSourceType(allowedFields.contains(SOURCE_TYPE_FIELD) ? source.getSourceType() : null);
        target.setSection(allowedFields.contains(SECTION_FIELD) ? source.getSection() : null);
        target.setPage(allowedFields.contains(PAGE_FIELD) ? source.getPage() : null);
        target.setSourceUri(allowedFields.contains(SOURCE_URI_FIELD) ? safeSourceUri(source.getSourceUri()) : null);
        target.setSnippet(allowedFields.contains(SNIPPET_FIELD) ? source.getSnippet() : null);
        if (allowedFields.contains(CONTENT_FIELD)) {
            target.setContent(source.getContent());
            target.setContextBefore(source.getContextBefore());
            target.setContextAfter(source.getContextAfter());
        }
        target.setChunkIndex(source.getChunkIndex());
        target.setCharStart(source.getCharStart());
        target.setCharEnd(source.getCharEnd());
        target.setKeywordRank(source.getKeywordRank());
        target.setVectorRank(source.getVectorRank());
        target.setRrfScore(source.getRrfScore());
        target.setRetrievalChannels(source.getRetrievalChannels());
        target.setScore(source.getScore());
        return target;
    }

    private static String safeSourceUri(String sourceUri) {
        if (sourceUri == null || sourceUri.isBlank()) {
            return sourceUri;
        }
        int queryIndex = sourceUri.indexOf('?');
        int fragmentIndex = sourceUri.indexOf('#');
        int end = sourceUri.length();
        if (queryIndex >= 0) {
            end = Math.min(end, queryIndex);
        }
        if (fragmentIndex >= 0) {
            end = Math.min(end, fragmentIndex);
        }
        return sourceUri.substring(0, end);
    }

    private static String citationId(AdapterDocumentEvidence evidence) {
        if (evidence.getChunkId() != null && !evidence.getChunkId().isBlank()) {
            return evidence.getChunkId();
        }
        return evidence.getDocumentId();
    }

    private static String text(AdapterDocumentEvidence evidence) {
        if (evidence.getContent() != null && !evidence.getContent().isBlank()) {
            return evidence.getContent();
        }
        return evidence.getSnippet();
    }
}
