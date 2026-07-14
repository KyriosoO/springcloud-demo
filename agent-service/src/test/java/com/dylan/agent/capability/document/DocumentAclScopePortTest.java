package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentCorpusKey;
import com.dylan.agent.adapter.api.operation.CapabilityOperationContext;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.api.plan.DocumentPlanOperation;
import com.dylan.agent.capability.document.acl.*;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.kernel.core.DocumentCapabilityHandlerTestSupport;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DocumentAclScopePortTest {
    private static final Instant NOW = Instant.parse("2026-07-07T12:00:00Z");

    @Test
    void typedAllowResponseProducesCurrentScopeAndOmitsProfileAliasInputs() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://document-acl");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        HttpDocumentAclScopeClient client = client(builder.build());
        server.expect(requestTo("http://document-acl/internal/document-acl/scope/resolve"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer svc-token"))
                .andExpect(header("X-Agent-Request-Id", "corr-1"))
                .andExpect(header("X-Agent-Operation-Id", "op-1"))
                .andExpect(jsonPath("$.invocationId").value("inv-1"))
                .andExpect(jsonPath("$.subjectType").value("user"))
                .andExpect(jsonPath("$.domain").value("policy_document"))
                .andExpect(jsonPath("$.profileProjectionDigest").value("c".repeat(64)))
                .andExpect(jsonPath("$.retrievalProfile").doesNotExist())
                .andExpect(jsonPath("$.profileVersion").doesNotExist())
                .andExpect(jsonPath("$.indexAlias").doesNotExist())
                .andRespond(withSuccess(allowedResponse("u-1"), MediaType.APPLICATION_JSON));

        DocumentAclScopeResolution resolution = client.resolve(request(() -> false));

        assertThat(resolution).isInstanceOf(DocumentAclScopeAllowed.class);
        DocumentAclScopeAllowed allowed = (DocumentAclScopeAllowed) resolution;
        assertThat(allowed.scope().subjectPrincipalId()).isEqualTo("principal-u-1");
        assertThat(allowed.scope().locallyComputedCanonicalDigest()).hasSize(64);
        assertThat(allowed.metadata().providerAttempts()).isEqualTo(1);
        server.verify();
    }

    @Test
    void responseBindingMismatchReturnsTypedFailure() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://document-acl");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        HttpDocumentAclScopeClient client = client(builder.build());
        server.expect(requestTo("http://document-acl/internal/document-acl/scope/resolve"))
                .andRespond(withSuccess(allowedResponse("other"), MediaType.APPLICATION_JSON));

        DocumentAclScopeResolution resolution = client.resolve(request(() -> false));

        assertThat(resolution).isInstanceOfSatisfying(DocumentAclScopeFailed.class,
                failure -> assertThat(failure.code()).isEqualTo(DocumentAclFailureCode.BINDING_MISMATCH));
        server.verify();
    }

    @Test
    void cancellationBeforeCallReturnsTypedZeroAttemptFailure() {
        HttpDocumentAclScopeClient client = client(RestClient.builder().build());

        DocumentAclScopeResolution resolution = client.resolve(request(() -> true));

        assertThat(resolution).isInstanceOfSatisfying(DocumentAclScopeFailed.class, failure -> {
            assertThat(failure.code()).isEqualTo(DocumentAclFailureCode.CANCELLED);
            assertThat(failure.metadata().providerAttempts()).isZero();
        });
    }

    @Test
    void scopeRejectsControlCharactersBeforeCanonicalization() {
        assertThatThrownBy(() -> new DocumentAclScopeSnapshot(
                "tenant\nother", "principal", java.util.Set.of(), java.util.Set.of(), java.util.Set.of(),
                new AllPrincipalVisibleDocuments(), java.util.Set.of(), "acl-v1", "perm-v1",
                NOW.minusSeconds(1), NOW.plusSeconds(30), "evidence", "a".repeat(64)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("non-canonical");
    }

    @Test
    void evidenceFactoryRejectsMismatchedOperationMetadata() {
        DocumentAclScopeRequest request = request(() -> false);
        DocumentAclScopeSnapshot scope = new DocumentAclScopeSnapshot(
                "tenant", "principal", java.util.Set.of(), java.util.Set.of(), java.util.Set.of(),
                new AllPrincipalVisibleDocuments(), java.util.Set.of(), "acl-v1", "perm-v1",
                NOW.minusSeconds(1), NOW.plusSeconds(30), "evidence", "a".repeat(64));
        var metadata = new com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata(
                "wrong-operation", request.operationContext().operationType(),
                new com.dylan.agent.adapter.api.operation.ProviderSafeIdentity("acl", java.util.Optional.empty()),
                1, 1, com.dylan.agent.adapter.api.operation.CapabilityOperationTermination.SUCCEEDED,
                "diagnostic", request.operationContext().resourceLimits().reference(), false, false, false);

        assertThatThrownBy(() -> new DocumentAclExecutionEvidenceFactory().create(request, scope, metadata))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("source binding");
    }

    private static HttpDocumentAclScopeClient client(RestClient restClient) {
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn("svc-token");
        return new HttpDocumentAclScopeClient(
                restClient, new DocumentAclAuthorityCredentialProvider(tokenProvider), new ObjectMapper(),
                Clock.fixed(NOW, ZoneOffset.UTC), DocumentAclCompilerLimits.secureDefaults());
    }

    private static DocumentAclScopeRequest request(
            com.dylan.agent.adapter.api.operation.CancellationSignal cancellation) {
        var limits = DocumentCapabilityHandlerTestSupport.executionScope().resourceLimits();
        var context = new CapabilityOperationContext(
                "inv-1", "corr-1", "document.search", "op-1",
                CapabilityOperationType.of("DOCUMENT_ACL_SCOPE"), NOW.plusSeconds(30), cancellation, limits);
        return new DocumentAclScopeRequest(
                context, "document-reg", new ExecutionSubjectRef("user", "u-1"),
                new DocumentCorpusKey("policy_document", "tax_policy"), DocumentPlanOperation.SEARCH,
                new PermissionEvidenceReference("perm-evidence", "perm-v1"), "c".repeat(64));
    }

    private static String allowedResponse(String subjectId) {
        return """
                {
                  "outcome":"ALLOWED",
                  "invocationId":"inv-1",
                  "requestCorrelationId":"corr-1",
                  "operationId":"op-1",
                  "registrationIdentity":"document-reg",
                  "subjectType":"user",
                  "subjectId":"%s",
                  "domain":"policy_document",
                  "materialType":"tax_policy",
                  "operation":"SEARCH",
                  "permissionEvidenceId":"perm-evidence",
                  "permissionVersion":"perm-v1",
                  "profileProjectionDigest":"%s",
                  "tenantId":"tenant-1",
                  "subjectPrincipalId":"principal-u-1",
                  "departmentIds":["dept-1"],
                  "roleIds":["role-1"],
                  "attributeKeys":[],
                  "documentIdConstraint":"ALL_PRINCIPAL_VISIBLE",
                  "allowedDocumentIds":[],
                  "deniedDocumentIds":[],
                  "authorityVersion":"acl-v1",
                  "issuedAt":"2026-07-07T11:59:00Z",
                  "expiresAt":"2026-07-07T12:20:00Z",
                  "authorityEvidenceRef":"authority-evidence-1",
                  "diagnosticId":"acl-diagnostic-1"
                }
                """.formatted(subjectId, "c".repeat(64));
    }
}
