package com.dylan.agent.capability.document.evidence;

import com.dylan.agent.adapter.api.document.DocumentCandidateIdentity;
import com.dylan.agent.adapter.api.document.DocumentCandidateSecurityBinding;
import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.security.AclBoundDocumentHit;
import com.dylan.agent.adapter.api.document.DocumentAclObjectRef;
import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.document.DocumentTargetBindingReference;
import com.dylan.agent.adapter.api.operation.ResourceLimitReference;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentEvidenceSelectorTest {

    private final DocumentEvidenceSelector selector = new DocumentEvidenceSelector();

    @Test
    void stopsAtFirstChunkLimitViolationInsteadOfSkippingPastStablePrefix() {
        List<AclBoundDocumentHit> ordered = List.of(
                hit("c1", "doc-1", 0, "甲"),
                hit("c2", "doc-1", 1, "乙"),
                hit("c3", "doc-2", 0, "丙"));

        SelectedDocumentEvidence selected = selector.select(ordered, limits(10, 100, 20, 1, 10));

        assertThat(selected.items()).extracting(AclBoundDocumentHit::candidateId).containsExactly("c1");
        assertThat(selected.truncated()).isTrue();
    }

    @Test
    void appliesUnicodeCodePointAndSnippetBudgetsWithoutSplittingSurrogatePairs() {
        AclBoundDocumentHit hit = hit("c1", "doc-1", 0, "😀甲乙");

        SelectedDocumentEvidence selected = selector.select(List.of(hit), limits(10, 4, 2, 2, 10));

        assertThat(selected.items()).hasSize(1);
        assertThat(selected.items().getFirst().citationText()).isEqualTo("😀甲");
        assertThat(selected.evidenceChars()).isEqualTo(4);
        assertThat(selected.truncated()).isTrue();
    }

    @Test
    void rejectsDuplicateCandidateIdentityBeforeSelection() {
        AclBoundDocumentHit duplicate = hit("c1", "doc-2", 0, "乙");

        org.assertj.core.api.Assertions.assertThatThrownBy(() -> selector.select(
                List.of(hit("c1", "doc-1", 0, "甲"), duplicate), limits(10, 100, 20, 2, 10)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("duplicate");
    }

    @Test
    void returnsNoEvidenceWhenEffectiveCitationBudgetIsZero() {
        SelectedDocumentEvidence selected = selector.select(
                List.of(hit("c1", "doc-1", 0, "甲")), limits(0, 100, 20, 2, 10));

        assertThat(selected.items()).isEmpty();
        assertThat(selected.evidenceChars()).isZero();
        assertThat(selected.truncated()).isTrue();
    }

    private static DocumentResourceLimit limits(int citationCount,
                                                int evidenceChars,
                                                int snippetChars,
                                                int chunksPerDocument,
                                                int returnedDocuments) {
        return new DocumentResourceLimit(
                new DocumentResourceLimit.DocumentInputLimit(100, 0),
                new DocumentResourceLimit.DocumentRetrievalLimit(2, 10, 10, chunksPerDocument, returnedDocuments),
                new DocumentResourceLimit.DocumentEnhancementLimit(0, 0, 0, 0),
                new DocumentResourceLimit.DocumentEvidenceOutputLimit(
                        10, evidenceChars, snippetChars, 0, citationCount, 0, 0, 0, 10_000L));
    }

    private static AclBoundDocumentHit hit(String candidateId,
                                           String documentId,
                                           int chunkIndex,
                                           String citationText) {
        return new AclBoundDocumentHit(
                candidateId,
                new DocumentCandidateIdentity(documentId, "v1", candidateId, chunkIndex),
                "题", "policy", "节", null, null, citationText, citationText, citationText,
                citationText, List.of(), List.of(), null, null, BigDecimal.ONE, BigDecimal.ONE,
                List.of("BM25"), List.of(), new DocumentCandidateSecurityBinding(
                        "inv-1", "corr-1", "document-reg", new DocumentCorpusKey("policy", "document"),
                        new DocumentTargetBindingReference("3.0.0", "1".repeat(64), "2".repeat(64), "3".repeat(64)),
                        "4".repeat(64), "5".repeat(64), new DocumentAclObjectRef("acl-1", "v1"),
                        "6".repeat(64), new ResourceLimitReference(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                        "7".repeat(64), "inv-1", "document-reg")));
    }
}
