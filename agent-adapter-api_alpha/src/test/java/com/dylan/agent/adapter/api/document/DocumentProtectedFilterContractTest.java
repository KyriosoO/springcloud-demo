package com.dylan.agent.adapter.api.document;

import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentProtectedFilterContractTest {
    @Test
    void anyTermsRejectsMissingFieldAtContractBoundary() {
        assertThatThrownBy(() -> new DocumentAnyTerms(null, Set.of("value")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("complete");
    }

    @Test
    void protectedBindingRejectsNonCanonicalDigests() {
        assertThatThrownBy(() -> new DocumentProtectedFilterBinding(
                new DocumentCorpusKey("policy", "document"),
                new DocumentExactTerm(DocumentAclIndexField.STATUS, "ACTIVE"),
                "not-a-digest", "a".repeat(64), "b".repeat(64),
                new com.dylan.agent.adapter.api.operation.ResourceLimitReference(
                        com.dylan.agent.api.contract.common.AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                        "c".repeat(64), "inv-1", "registration")))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
