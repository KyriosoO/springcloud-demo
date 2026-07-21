package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.api.response.AgentDocumentCitation;
import com.dylan.agent.api.response.AgentDocumentHit;
import com.dylan.agent.api.response.AgentDocumentResult;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.List;

/** 最终public DTO的UTF-8 exact byte gate；只在无可见生成文本时允许尾部成对缩减。 */
public final class DocumentResultSizeGuard {
    private final ObjectMapper mapper;
    public DocumentResultSizeGuard(ObjectMapper mapper) { this.mapper = mapper; }

    public boolean fits(DocumentAgentResultPayload payload, long maxBytes) {
        try { return mapper.writeValueAsBytes(payload).length <= maxBytes; }
        catch (Exception ex) { throw new IllegalStateException("document result serialization failed", ex); }
    }

    public int reduceEvidenceOnly(DocumentAgentResultPayload payload, long maxBytes) {
        AgentDocumentResult result = payload.getDocumentResult();
        if (hasVisibleGeneratedText(result)) throw new IllegalStateException("generated document result cannot remove bound evidence");
        List<AgentDocumentHit> hits = new ArrayList<>(result.getHits() == null ? List.of() : result.getHits());
        List<AgentDocumentCitation> citations = new ArrayList<>(result.getCitations() == null ? List.of() : result.getCitations());
        if (hits.size() != citations.size()) throw new IllegalStateException("document hit/citation pair mismatch");
        while (!fits(payload, maxBytes) && !hits.isEmpty()) {
            hits.removeLast(); citations.removeLast();
            result.setHits(List.copyOf(hits)); result.setCitations(List.copyOf(citations));
            if (result.getCoverage() != null) {
                result.getCoverage().setEvidenceCount(citations.size());
                result.getCoverage().setCoveredDocumentCount((int) citations.stream()
                        .map(AgentDocumentCitation::getDocumentId).distinct().count());
                result.getCoverage().setTruncated(true);
            }
        }
        if (!fits(payload, maxBytes)) throw new IllegalStateException("document result cannot fit effective byte limit");
        return hits.size();
    }

    private static boolean hasVisibleGeneratedText(AgentDocumentResult result) {
        return notBlank(result.getAnswerText()) || notBlank(result.getSummaryText())
                || result.getSummaryBullets() != null && result.getSummaryBullets().stream().anyMatch(DocumentResultSizeGuard::notBlank);
    }
    private static boolean notBlank(String value) { return value != null && !value.isBlank(); }
}
