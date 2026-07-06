package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;

class DocumentAgentAdapterTest {

    @Test
    void failsClosedWhenAclScopeMissing() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        DocumentAgentAdapter adapter = new DocumentAgentAdapter(
                client,
                new DocumentRetrievalMapper(new com.fasterxml.jackson.databind.ObjectMapper()),
                new DocumentEvidenceMapper(new com.fasterxml.jackson.databind.ObjectMapper(), new DocumentAdapterProperties()),
                new DocumentAdapterProperties());

        assertThatThrownBy(() -> adapter.retrieve(new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                "policy_document",
                "休假政策",
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                false)))
                .isInstanceOf(AgentAdapterException.class)
                .hasMessageContaining("ACL");
        verifyNoInteractions(client);
    }
}
