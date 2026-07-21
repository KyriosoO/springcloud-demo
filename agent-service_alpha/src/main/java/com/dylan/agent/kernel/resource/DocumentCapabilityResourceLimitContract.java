package com.dylan.agent.kernel.resource;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.Set;

/** DocumentResourceLimit@1.0.0 的 DLRL-1 求交、单调性与canonical digest。 */
public final class DocumentCapabilityResourceLimitContract
        implements CapabilityResourceLimitContract<DocumentResourceLimit> {
    private static final Set<ResourceLimitDimension> DIMENSIONS = dimensions();

    @Override public ContractRef contractRef() { return AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT; }
    @Override public Class<DocumentResourceLimit> limitType() { return DocumentResourceLimit.class; }
    @Override public Set<ResourceLimitDimension> supportedDimensions() { return DIMENSIONS; }
    @Override public void validate(DocumentResourceLimit value) {
        if (value == null) throw new IllegalArgumentException("document resource limit must not be null");
        Math.multiplyExact((long) value.output().maxEvidenceCount(), value.output().maxEvidenceChars());
        Math.multiplyExact((long) value.output().maxSummaryBullets(), value.output().maxSummaryChars());
    }
    @Override public DocumentResourceLimit intersect(DocumentResourceLimit left, DocumentResourceLimit right) { validate(left); validate(right); return left.stricterOf(right); }
    @Override public boolean isSameOrStricter(DocumentResourceLimit candidate, DocumentResourceLimit baseline) { validate(candidate); validate(baseline); return candidate.equals(candidate.stricterOf(baseline)); }
    @Override public String canonicalDigest(DocumentResourceLimit value) {
        validate(value);
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            update(digest, "DLRL-1",
                    value.input().maxQueryChars(), value.input().maxCallerFilterCount(),
                    value.retrieval().maxChannelCount(), value.retrieval().maxCandidatesPerChannel(),
                    value.retrieval().maxFusedCandidates(), value.retrieval().maxChunksPerDocument(),
                    value.retrieval().maxReturnedDocuments(), value.enhancement().maxRewriteCandidates(),
                    value.enhancement().maxEmbeddingTexts(), value.enhancement().maxEmbeddingDimensions(),
                    value.enhancement().maxRerankCandidates(), value.output().maxEvidenceCount(),
                    value.output().maxEvidenceChars(), value.output().maxSnippetChars(),
                    value.output().maxContextChars(), value.output().maxCitationCount(),
                    value.output().maxGeneratedChars(), value.output().maxSummaryChars(),
                    value.output().maxSummaryBullets(), value.output().maxResultBytes());
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) { throw new IllegalStateException("SHA-256 unavailable", ex); }
    }

    private static void update(MessageDigest digest, Object... values) {
        for (Object value : values) {
            byte[] bytes = String.valueOf(value).getBytes(StandardCharsets.UTF_8);
            digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
            digest.update(bytes);
        }
    }

    private static Set<ResourceLimitDimension> dimensions() {
        LinkedHashSet<ResourceLimitDimension> result = new LinkedHashSet<>();
        String[] ids = {
                "document.input.query-chars", "document.input.caller-filter-count",
                "document.retrieval.channel-count", "document.retrieval.candidates-per-channel",
                "document.retrieval.fused-candidates", "document.retrieval.chunks-per-document",
                "document.retrieval.returned-documents", "document.enhancement.rewrite-candidates",
                "document.enhancement.embedding-texts", "document.enhancement.embedding-dimensions",
                "document.enhancement.rerank-candidates", "document.output.evidence-count",
                "document.output.evidence-chars", "document.output.snippet-chars",
                "document.output.context-chars", "document.output.citation-count",
                "document.output.generated-chars", "document.output.summary-chars",
                "document.output.summary-bullets", "document.output.result-bytes"};
        for (String id : ids) result.add(new ResourceLimitDimension(id));
        return Set.copyOf(result);
    }
}
