package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.util.List;
import java.util.Objects;

/** LLM 输入前的最小安全过滤。 */
public class DocumentEvidencePreSecurityFilter {

    public List<AdapterDocumentEvidence> filter(
            List<AdapterDocumentEvidence> evidence,
            ExecutionScope scope,
            String domain) {
        if (scope != null && (!scope.allowedDomains().contains(domain)
                || scope.allowedFields().getOrDefault(domain, java.util.Set.of()).isEmpty())) {
            return List.of();
        }
        return (evidence == null ? List.<AdapterDocumentEvidence>of() : evidence).stream()
                .filter(Objects::nonNull)
                .filter(item -> citationId(item) != null)
                .filter(item -> text(item) != null && !text(item).isBlank())
                .toList();
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
