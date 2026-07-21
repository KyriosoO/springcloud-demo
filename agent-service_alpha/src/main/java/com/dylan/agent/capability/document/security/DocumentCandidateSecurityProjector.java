package com.dylan.agent.capability.document.security;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.capability.document.acl.DocumentAclExecutionEvidence;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/** AclBound Adapter evidence 到 Provider/Result 可消费 Safe candidate 的唯一投影器。 */
public final class DocumentCandidateSecurityProjector {
    public List<SafeDocumentCandidate> project(
            List<AclBoundDocumentHit> hits,
            DocumentAclExecutionEvidence evidence,
            DocumentResourceLimit limits) {
        List<AclBoundDocumentHit> source = List.copyOf(hits == null ? List.of() : hits);
        if (source.size() > limits.retrieval().maxFusedCandidates()) {
            throw new IllegalArgumentException("document safe candidate count exceeds limit");
        }
        List<SafeDocumentCandidate> result = new ArrayList<>(source.size());
        for (AclBoundDocumentHit hit : source) result.add(project(hit, evidence, limits));
        return List.copyOf(result);
    }

    private SafeDocumentCandidate project(
            AclBoundDocumentHit hit,
            DocumentAclExecutionEvidence evidence,
            DocumentResourceLimit limits) {
        Objects.requireNonNull(hit, "document hit must not be null");
        DocumentCandidateSecurityBinding binding = Objects.requireNonNull(
                hit.securityBinding(), "document hit security binding must not be null");
        if (!binding.invocationId().equals(evidence.invocationId())
                || !binding.requestCorrelationId().equals(evidence.requestCorrelationId())
                || !binding.registrationIdentity().equals(evidence.registrationIdentity())
                || !binding.corpusKey().equals(evidence.corpusKey())
                || !binding.aclEvidenceDigest().equals(evidence.canonicalDigest())
                || !binding.profileProjectionDigest().equals(evidence.profileProjectionDigest())
                || !binding.resourceLimitReference().equals(evidence.resourceLimitReference())) {
            throw new IllegalArgumentException("document hit security binding mismatch");
        }
        DocumentCandidateIdentity identity = hit.identity();
        String snippet = bounded(hit.snippet(), limits.output().maxSnippetChars(), "snippet");
        String context = bounded(joinContext(hit), limits.output().maxContextChars(), "context");
        String sourceUri = DocumentSafeSourceUri.sanitize(hit.sourceUri());
        BigDecimal score = hit.rrfScore() == null ? hit.score() : hit.rrfScore();
        if (score == null || !Double.isFinite(score.doubleValue())) {
            throw new IllegalArgumentException("document candidate score is invalid");
        }
        return new SafeDocumentCandidate(
                requireText(hit.candidateId(), "candidateId"), identity, hit.title(), hit.section(),
                hit.page(), snippet, context, sourceUri, hit.safeFieldNames().stream().sorted().toList(),
                hit.retrievalChannels(), score.doubleValue(), binding);
    }

    private static String joinContext(AclBoundDocumentHit hit) {
        List<String> values = new ArrayList<>();
        values.addAll(hit.contextBefore());
        if (hit.content() != null && !hit.content().isBlank()) values.add(hit.content());
        values.addAll(hit.contextAfter());
        return values.isEmpty() ? null : String.join("\n", values);
    }

    private static String bounded(String value, int maxChars, String field) {
        if (value == null) return null;
        if (value.codePointCount(0, value.length()) > maxChars) {
            throw new IllegalArgumentException("document " + field + " exceeds limit");
        }
        return value;
    }

    private static String requireText(String value, String field) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(field + " must not be blank");
        return value;
    }
}
