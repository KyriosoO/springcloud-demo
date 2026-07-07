package com.dylan.agent.capability.document;

import com.dylan.agent.capability.document.acl.DisabledDocumentAclScopePort;
import com.dylan.agent.capability.document.acl.DocumentAclScopeRequest;
import com.dylan.agent.capability.document.acl.HttpDocumentAclScopeClient;
import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import com.dylan.common.security.ServiceTokenProvider;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DocumentAclScopePortTest {

    @Test
    void disabledPortFailsClosed() {
        DisabledDocumentAclScopePort port = new DisabledDocumentAclScopePort();

        assertThatThrownBy(() -> port.resolve(new DocumentAclScopeRequest(
                "inv-1",
                "user:u-1",
                "policy_document",
                "perm-evidence",
                "perm-v1",
                Instant.now().plusSeconds(30))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("disabled");
    }

    @Test
    void httpClientFailsClosedWhenPermissionEvidenceIsMissing() {
        HttpDocumentAclScopeClient client = new HttpDocumentAclScopeClient(
                RestClient.builder().build(),
                authHeaderProvider());

        assertThatThrownBy(() -> client.resolve(new DocumentAclScopeRequest(
                "inv-1",
                "user:u-1",
                "policy_document",
                null,
                "perm-v1",
                Instant.now().plusSeconds(30))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("permissionEvidenceId");
    }

    @Test
    void httpClientRejectsMismatchedReturnedSubjectOrDomain() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://document-acl");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        HttpDocumentAclScopeClient client = new HttpDocumentAclScopeClient(builder.build(), authHeaderProvider());
        server.expect(requestTo("http://document-acl/internal/document-acl/scope/resolve"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer svc-token"))
                .andExpect(header("X-Agent-Request-Id", "inv-1"))
                .andExpect(header("X-Agent-Deadline", "2026-07-07T12:05:00Z"))
                .andExpect(jsonPath("$.invocationId").value("inv-1"))
                .andExpect(jsonPath("$.requestId").doesNotExist())
                .andExpect(jsonPath("$.subjectRef").value("user:u-1"))
                .andExpect(jsonPath("$.domain").value("company_policy"))
                .andRespond(withSuccess("""
                        {
                          "tenantId": "tenant-1",
                          "userId": "u-1",
                          "departmentIds": [],
                          "roleIds": [],
                          "attributeKeys": [],
                          "aclSnapshotVersion": "acl-v1",
                          "expiresAt": "2026-07-07T12:30:00Z",
                          "subjectRef": "user:other",
                          "domain": "company_policy"
                        }
                        """, MediaType.APPLICATION_JSON));

        assertThatThrownBy(() -> client.resolve(new DocumentAclScopeRequest(
                "inv-1",
                "user:u-1",
                "company_policy",
                "perm-evidence",
                "perm-v1",
                Instant.parse("2026-07-07T12:05:00Z"))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("subjectRef mismatch");
        server.verify();
    }

    private DocumentProviderAuthHeaderProvider authHeaderProvider() {
        ServiceTokenProvider serviceTokenProvider = mock(ServiceTokenProvider.class);
        when(serviceTokenProvider.token()).thenReturn("svc-token");
        return new DocumentProviderAuthHeaderProvider(serviceTokenProvider);
    }
}
