package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Objects;
import java.util.Set;

/** 按 current ExecutionScope 形成公开结果可见证据，不改变候选顺序和安全绑定。 */
public final class DocumentEvidenceVisibilityProjector {
    private static final String CONTENT = "content";
    private static final String SNIPPET = "snippet";
    private static final String TITLE = "title";
    private static final String SOURCE_TYPE = "sourceType";
    private static final String SECTION = "section";
    private static final String PAGE = "page";
    private static final String SOURCE_URI = "sourceUri";

    public List<AclBoundDocumentHit> project(
            List<AclBoundDocumentHit> evidence,
            ExecutionScope scope,
            String domain) {
        Objects.requireNonNull(scope, "executionScope must not be null");
        Objects.requireNonNull(domain, "domain must not be null");
        Set<String> allowed = scope.allowedFields().getOrDefault(domain, Set.of());
        if (!scope.allowedDomains().contains(domain)
                || (!allowed.contains(CONTENT) && !allowed.contains(SNIPPET))) {
            return List.of();
        }
        return (evidence == null ? List.<AclBoundDocumentHit>of() : evidence).stream()
                .map(hit -> sanitize(hit, allowed))
                .filter(hit -> {
                    String text = text(hit);
                    return text != null && !text.isBlank();
                })
                .toList();
    }

    private static AclBoundDocumentHit sanitize(AclBoundDocumentHit hit, Set<String> allowed) {
        return new AclBoundDocumentHit(
                hit.candidateId(), hit.identity(),
                allowed.contains(TITLE) ? hit.title() : null,
                allowed.contains(SOURCE_TYPE) ? hit.sourceType() : null,
                allowed.contains(SECTION) ? hit.section() : null,
                allowed.contains(PAGE) ? hit.page() : null,
                allowed.contains(SOURCE_URI) ? safeUri(hit.sourceUri()) : null,
                allowed.contains(SNIPPET) ? hit.snippet() : null,
                allowed.contains(CONTENT) ? hit.content() : null,
                allowed.contains(SNIPPET) ? hit.citationText() : null,
                allowed.contains(CONTENT) ? hit.generationText() : null,
                allowed.contains(CONTENT) ? hit.contextBefore() : List.of(),
                allowed.contains(CONTENT) ? hit.contextAfter() : List.of(),
                hit.charStart(), hit.charEnd(), hit.score(), hit.rrfScore(), hit.retrievalChannels(),
                hit.safeFieldNames(), hit.securityBinding());
    }

    private static String safeUri(String value) {
        if (value == null || value.isBlank()) return value;
        int query = value.indexOf('?');
        int fragment = value.indexOf('#');
        int end = value.length();
        if (query >= 0) end = Math.min(end, query);
        if (fragment >= 0) end = Math.min(end, fragment);
        return value.substring(0, end);
    }

    private static String text(AclBoundDocumentHit hit) {
        if (hit.generationText() != null && !hit.generationText().isBlank()) return hit.generationText();
        if (hit.content() != null && !hit.content().isBlank()) return hit.content();
        if (hit.citationText() != null && !hit.citationText().isBlank()) return hit.citationText();
        return hit.snippet();
    }
}
