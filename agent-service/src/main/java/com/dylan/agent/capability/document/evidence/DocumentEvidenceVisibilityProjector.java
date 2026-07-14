package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.capability.document.security.DocumentSafeSourceUri;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.result.ResultValueMaskingSupport;

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
    private final ResultValueMaskingSupport masking;

    public DocumentEvidenceVisibilityProjector(ResultValueMaskingSupport masking) {
        this.masking = Objects.requireNonNull(masking, "masking must not be null");
    }

    public List<AclBoundDocumentHit> project(
            List<AclBoundDocumentHit> evidence,
            ExecutionScope scope,
            String domain) {
        Objects.requireNonNull(scope, "executionScope must not be null");
        Objects.requireNonNull(domain, "domain must not be null");
        Set<String> allowed = masking.allowedFields(domain, scope);
        if (!scope.allowedDomains().contains(domain)
                || (!allowed.contains(CONTENT) && !allowed.contains(SNIPPET))) {
            return List.of();
        }
        return (evidence == null ? List.<AclBoundDocumentHit>of() : evidence).stream()
                .map(hit -> sanitize(hit, allowed, scope, domain))
                .filter(hit -> {
                    String text = text(hit);
                    return text != null && !text.isBlank();
                })
                .toList();
    }

    private AclBoundDocumentHit sanitize(
            AclBoundDocumentHit hit,
            Set<String> allowed,
            ExecutionScope scope,
            String domain) {
        return new AclBoundDocumentHit(
                hit.candidateId(), hit.identity(),
                stringValue(domain, TITLE, hit.title(), allowed, scope),
                stringValue(domain, SOURCE_TYPE, hit.sourceType(), allowed, scope),
                stringValue(domain, SECTION, hit.section(), allowed, scope),
                integerValue(domain, PAGE, hit.page(), allowed, scope),
                allowed.contains(SOURCE_URI) ? DocumentSafeSourceUri.sanitize(
                        masking.maskStringValue(domain, SOURCE_URI, hit.sourceUri(), scope)) : null,
                stringValue(domain, SNIPPET, hit.snippet(), allowed, scope),
                stringValue(domain, CONTENT, hit.content(), allowed, scope),
                stringValue(domain, SNIPPET, hit.citationText(), allowed, scope),
                stringValue(domain, CONTENT, hit.generationText(), allowed, scope),
                allowed.contains(CONTENT) ? maskValues(domain, CONTENT, hit.contextBefore(), scope) : List.of(),
                allowed.contains(CONTENT) ? maskValues(domain, CONTENT, hit.contextAfter(), scope) : List.of(),
                hit.charStart(), hit.charEnd(), hit.score(), hit.rrfScore(), hit.retrievalChannels(),
                hit.safeFieldNames(), hit.securityBinding());
    }

    private String stringValue(
            String domain, String field, String value, Set<String> allowed, ExecutionScope scope) {
        return allowed.contains(field) ? masking.maskStringValue(domain, field, value, scope) : null;
    }
    private Integer integerValue(
            String domain, String field, Integer value, Set<String> allowed, ExecutionScope scope) {
        if (!allowed.contains(field)) return null;
        Object masked = masking.maskValue(domain, field, value, scope);
        if (masked == null || masked instanceof Integer) return (Integer) masked;
        throw new IllegalArgumentException("document evidence numeric mask type mismatch");
    }
    private List<String> maskValues(
            String domain, String field, List<String> values, ExecutionScope scope) {
        return values.stream().map(value -> masking.maskStringValue(domain, field, value, scope)).toList();
    }

    private static String text(AclBoundDocumentHit hit) {
        if (hit.generationText() != null && !hit.generationText().isBlank()) return hit.generationText();
        if (hit.content() != null && !hit.content().isBlank()) return hit.content();
        if (hit.citationText() != null && !hit.citationText().isBlank()) return hit.citationText();
        return hit.snippet();
    }
}
