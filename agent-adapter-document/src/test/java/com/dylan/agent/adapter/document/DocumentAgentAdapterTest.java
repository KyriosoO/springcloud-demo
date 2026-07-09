package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.document.DocumentAclScope;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class DocumentAgentAdapterTest {

    @Test
    void failsClosedWhenAclScopeMissing() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        DocumentAgentAdapter adapter = adapter(client, properties(Map.of("company_policy", "agent-doc-company-policy")));

        assertThatThrownBy(() -> adapter.retrieve(request("company_policy", null)))
                .isInstanceOf(AgentAdapterException.class)
                .hasMessageContaining("ACL");
        verifyNoInteractions(client);
    }

    @Test
    void usesConfiguredIndexByDomain() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        when(client.search(eq("agent-doc-company-policy"), anyString()))
                .thenReturn("{\"hits\":{\"hits\":[]}}");
        DocumentAgentAdapter adapter = adapter(client, properties(Map.of(
                "company_policy", "agent-doc-company-policy")));

        var result = adapter.retrieve(request("company_policy", aclScope()));

        assertThat(result.getHits()).isEmpty();
        verify(client).search(eq("agent-doc-company-policy"), anyString());
    }

    @Test
    void requestIndexAliasOverridesDomainDefaultIndex() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        when(client.search(eq("agent-doc-tax-policy-read"), anyString()))
                .thenReturn("{\"hits\":{\"hits\":[]}}");
        DocumentAgentAdapter adapter = adapter(client, properties(Map.of(
                "company_policy", "agent-doc-company-policy")));

        var result = adapter.retrieve(aliasRequest("company_policy", "agent-doc-tax-policy-read", aclScope()));

        assertThat(result.getHits()).isEmpty();
        verify(client).search(eq("agent-doc-tax-policy-read"), anyString());
    }

    @Test
    void rejectsMissingIndexByDomainWhenAclScopeExists() {
        DocumentSearchClient client = mock(DocumentSearchClient.class);
        DocumentAgentAdapter adapter = adapter(client, properties(Map.of(
                "knowledge_base", "agent-doc-knowledge-base")));

        assertThatThrownBy(() -> adapter.retrieve(request("company_policy", aclScope())))
                .isInstanceOf(AgentAdapterException.class)
                .hasMessageContaining("read alias");
        verifyNoInteractions(client);
    }

    private DocumentAgentAdapter adapter(DocumentSearchClient client, DocumentAdapterProperties properties) {
        return new DocumentAgentAdapter(
                client,
                new DocumentRetrievalMapper(new com.fasterxml.jackson.databind.ObjectMapper()),
                new DocumentEvidenceMapper(new com.fasterxml.jackson.databind.ObjectMapper(), properties),
                properties);
    }

    private DocumentAdapterProperties properties(Map<String, String> indexByDomain) {
        DocumentAdapterProperties properties = new DocumentAdapterProperties();
        properties.setIndexByDomain(indexByDomain);
        return properties;
    }

    private DocumentRetrievalRequest request(String domain, DocumentAclScope aclScope) {
        return new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                domain,
                "tax_policy",
                "tax-v2",
                "v2",
                null,
                "休假政策",
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                false,
                DocumentRetrievalMode.KEYWORD,
                List.of(),
                null,
                null,
                null).withAclScope(aclScope, "perm-evidence", "perm-v1");
    }

    private DocumentRetrievalRequest aliasRequest(String domain, String indexAlias, DocumentAclScope aclScope) {
        return new DocumentRetrievalRequest(
                DocumentPlanOperation.SEARCH,
                domain,
                "tax_policy",
                "tax-v2",
                "v2",
                indexAlias,
                "休假政策",
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                5,
                1,
                5,
                null,
                false,
                DocumentRetrievalMode.KEYWORD,
                List.of(),
                null,
                null,
                aclScope);
    }

    private DocumentAclScope aclScope() {
        return new DocumentAclScope(
                "tenant-1",
                "user-1",
                List.of("dept-1"),
                List.of("role-1"),
                List.of(),
                "acl-v1",
                Instant.now().plusSeconds(300));
    }
}
