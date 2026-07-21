package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.*;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.kernel.core.ExecutionContext;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

final class DocumentEvidenceTestFixtures {
    private DocumentEvidenceTestFixtures() {
    }

    static AclBoundDocumentHit evidence(
            String title,
            String section,
            Integer page,
            String sourceUri,
            String snippet,
            String content,
            String generationText,
            List<String> contextBefore,
            List<String> contextAfter,
            Integer chunkIndex,
            BigDecimal rrfScore) {
        ResourceLimitReference limits = new ResourceLimitReference(
                AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                "d".repeat(64), "inv-1", "document-reg");
        DocumentCandidateSecurityBinding security = new DocumentCandidateSecurityBinding(
                "inv-1", "corr-1", "document-reg", new DocumentCorpusKey("policy", "document"),
                new DocumentTargetBindingReference("3.0.0", "e".repeat(64), "f".repeat(64), "1".repeat(64)),
                "a".repeat(64), "b".repeat(64), new DocumentAclObjectRef("acl-1", "v1"),
                "c".repeat(64), limits);
        return new AclBoundDocumentHit(
                "candidate-1",
                new DocumentCandidateIdentity("doc-1", "v1", "c-1", chunkIndex == null ? 0 : chunkIndex),
                title, "policy", section, page, sourceUri, snippet, content, null, generationText,
                contextBefore, contextAfter, null, null, BigDecimal.ONE, rrfScore,
                List.of("BM25"), List.of(), security);
    }

    static DocumentRetrievalResponseBinding responseBinding(
            AclBoundDocumentHit hit,
            ValidatedDocumentPlan plan,
            ExecutionContext context) {
        DocumentCandidateSecurityBinding security = hit.securityBinding();
        return new DocumentRetrievalResponseBinding(
                security.requestCorrelationId(), "op-1", plan.selectedCorpus(), security.targetBinding(),
                plan.profile().profileProjectionDigest(), context.resourceLimits().reference(),
                context.executionScope().externalProcessingAuthorizationEvidence().canonicalDigest(),
                security.protectedFilterDigest(), security.aclEvidenceDigest());
    }
}
