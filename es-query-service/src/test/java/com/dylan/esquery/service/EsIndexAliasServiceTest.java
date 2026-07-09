package com.dylan.esquery.service;

import com.dylan.esquery.api.model.AliasSwitchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.HttpEntity;
import org.apache.http.StatusLine;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class EsIndexAliasServiceTest {

    @Test
    void rejectsAliasSwitchForNonDocumentIndex() {
        assertThatThrownBy(() -> service().switchReadAlias("orders", request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("document indexes");
    }

    @Test
    void rejectsAliasSwitchToNonDocumentTarget() {
        AliasSwitchRequest request = request();
        request.setTargetIndex("orders-v2");

        assertThatThrownBy(() -> service().switchReadAlias("agent-doc-policy", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("targetIndex must be a document index");
    }

    @Test
    void rejectsAliasSwitchWithNonDocumentExpectedPreviousIndex() {
        AliasSwitchRequest request = request();
        request.setExpectedPreviousIndex("orders-v1");

        assertThatThrownBy(() -> service().switchReadAlias("agent-doc-policy", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("expectedPreviousIndex must be a document index");
    }

    @Test
    void rejectsAliasSwitchBeforeTaskValidationPasses() {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("validation must be PASSED");
    }

    @Test
    void rejectsAliasSwitchWhenValidationDigestDoesNotMatchTask() {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");
        repository.markValidationPassed("task-1", "real-digest", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("validationDigest");
    }

    @Test
    void rejectsAliasSwitchWithDigestFromDifferentTask() {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");
        repository.markValidationPassed("task-1", "digest-1", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
        repository.create("task-2", "agent-doc-policy", "agent-doc-policy-v3", "FULL");
        repository.markSuccess("task-2");
        repository.markValidationPassed("task-2", "digest-from-task-2", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
        AliasSwitchRequest request = request();
        request.setValidationDigest("digest-from-task-2");

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("validationDigest");
    }

    @Test
    void rejectsAliasSwitchWhenCurrentAliasIsMissing() throws Exception {
        RestClient restClient = mock(RestClient.class);
        ResponseException notFound = mock(ResponseException.class);
        Response response = mock(Response.class);
        StatusLine statusLine = mock(StatusLine.class);
        when(statusLine.getStatusCode()).thenReturn(404);
        when(response.getStatusLine()).thenReturn(statusLine);
        when(notFound.getResponse()).thenReturn(response);
        when(restClient.performRequest(any())).thenThrow(notFound);
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");
        repository.markValidationPassed("task-1", "digest-1", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");

        assertThatThrownBy(() -> service(restClient, repository).switchReadAlias("agent-doc-policy", request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("expectedPreviousIndex");
        verify(restClient).performRequest(any());
    }

    @Test
    void switchesAliasWhenCurrentTargetMatchesExpectedPreviousIndex() throws Exception {
        RestClient restClient = mock(RestClient.class);
        RebuildTaskRepository repository = validatedRepository("task-1", "agent-doc-policy-v2", "digest-1");
        Response aliasResponse = aliasResponse("agent-doc-policy-v1");
        Response updateResponse = mock(Response.class);
        when(restClient.performRequest(any())).thenReturn(aliasResponse, updateResponse);

        service(restClient, repository).switchReadAlias("agent-doc-policy", request());

        ArgumentCaptor<org.elasticsearch.client.Request> captor =
                ArgumentCaptor.forClass(org.elasticsearch.client.Request.class);
        verify(restClient, org.mockito.Mockito.times(2)).performRequest(captor.capture());
        assertThat(captor.getAllValues().get(1).getEndpoint()).isEqualTo("/_aliases");
        String body = new String(captor.getAllValues().get(1).getEntity().getContent().readAllBytes(),
                StandardCharsets.UTF_8);
        assertThat(body).contains("\"remove\"");
        assertThat(body).contains("agent-doc-policy-v1");
        assertThat(body).contains("\"add\"");
        assertThat(body).contains("agent-doc-policy-v2");
    }

    @Test
    void treatsAliasAlreadyOnTargetAsIdempotentSuccess() throws Exception {
        RestClient restClient = mock(RestClient.class);
        RebuildTaskRepository repository = validatedRepository("task-1", "agent-doc-policy-v2", "digest-1");
        Response aliasResponse = aliasResponse("agent-doc-policy-v2");
        when(restClient.performRequest(any())).thenReturn(aliasResponse);
        EsIndexAliasService service = service(restClient, repository);

        service.switchReadAlias("agent-doc-policy", request());

        verify(restClient).performRequest(any());
        assertThat(service.aliasAudits()).singleElement()
                .satisfies(audit -> {
                    assertThat(audit.operation()).isEqualTo("SWITCH");
                    assertThat(audit.result()).isEqualTo("IDEMPOTENT");
                    assertThat(audit.domain()).isEqualTo("tax_policy");
                    assertThat(audit.materialType()).isEqualTo("policy");
                    assertThat(audit.profileVersion()).isEqualTo("profile-v1");
                    assertThat(audit.indexVersion()).isEqualTo("idx-v2");
                    assertThat(audit.goldSetVersion()).isEqualTo("gold-tax-v1");
                    assertThat(audit.validationReportIdPrefix()).isEqualTo("report-v2");
                    assertThat(audit.digestPrefix()).isEqualTo("digest-1");
                    assertThat(audit.operatorRefHash()).isNotBlank();
                    assertThat(audit.operatorRefHash()).isNotEqualTo("operator-1");
                });
    }

    @Test
    void rejectsRollbackTargetOutsideAliasHistory() {
        RestClient restClient = mock(RestClient.class);
        RebuildTaskRepository repository = validatedRepository("task-rollback", "agent-doc-policy-v1", "digest-rollback");
        AliasSwitchRequest request = request();
        request.setTaskId("task-rollback");
        request.setTargetIndex("agent-doc-policy-v1");
        request.setExpectedPreviousIndex("agent-doc-policy-v2");
        request.setValidationDigest("digest-rollback");
        EsIndexAliasService service = service(restClient, repository);

        assertThatThrownBy(() -> service.rollbackReadAlias("agent-doc-policy", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("trusted alias history");
        assertThat(service.aliasAudits()).singleElement()
                .extracting(AliasOperationAudit::result)
                .isEqualTo("FAILED");
    }

    @Test
    void rejectsAliasSwitchWithoutProfileAuditFields() {
        RebuildTaskRepository repository = validatedRepository("task-1", "agent-doc-policy-v2", "digest-1");
        AliasSwitchRequest request = request();
        request.setProfileVersion(null);

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("profileVersion");
    }

    @Test
    void switchesV2AliasOnlyAfterValidationReportFieldsArePresent() {
        RebuildTaskRepository repository = validatedRepository("task-1", "agent-doc-policy-v2", "digest-1");
        AliasSwitchRequest request = request();
        request.setGoldSetVersion(null);

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("goldSetVersion");
    }

    @Test
    void rollsBackAliasWhenCurrentTargetMatchesExpectedPreviousIndex() throws Exception {
        RestClient restClient = mock(RestClient.class);
        RebuildTaskRepository repository = validatedRepository("task-1", "agent-doc-policy-v2", "digest-1");
        repository.create("task-rollback", "agent-doc-policy", "agent-doc-policy-v1", "FULL");
        repository.markSuccess("task-rollback");
        repository.markValidationPassed("task-rollback", "digest-rollback", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
        Response updateResponse = mock(Response.class);
        Response switchAliasResponse = aliasResponse("agent-doc-policy-v1");
        Response rollbackAliasResponse = aliasResponse("agent-doc-policy-v2");
        when(restClient.performRequest(any())).thenReturn(
                switchAliasResponse,
                updateResponse,
                rollbackAliasResponse,
                updateResponse);
        EsIndexAliasService service = service(restClient, repository);
        service.switchReadAlias("agent-doc-policy", request());
        AliasSwitchRequest request = request();
        request.setTaskId("task-rollback");
        request.setTargetIndex("agent-doc-policy-v1");
        request.setExpectedPreviousIndex("agent-doc-policy-v2");
        request.setValidationDigest("digest-rollback");

        service.rollbackReadAlias("agent-doc-policy", request);

        ArgumentCaptor<org.elasticsearch.client.Request> captor =
                ArgumentCaptor.forClass(org.elasticsearch.client.Request.class);
        verify(restClient, org.mockito.Mockito.times(4)).performRequest(captor.capture());
        String body = new String(captor.getAllValues().get(3).getEntity().getContent().readAllBytes(),
                StandardCharsets.UTF_8);
        assertThat(body).contains("agent-doc-policy-v2");
        assertThat(body).contains("agent-doc-policy-v1");
        assertThat(service.aliasHistory()).hasSize(2);
    }

    @Test
    void rollsBackAliasWithPersistedHistoryAfterServiceRecreation() throws Exception {
        AliasOperationAuditRepository auditRepository = new InMemoryAliasOperationAuditRepository();
        RestClient switchRestClient = mock(RestClient.class);
        RebuildTaskRepository repository = validatedRepository("task-1", "agent-doc-policy-v2", "digest-1");
        repository.create("task-rollback", "agent-doc-policy", "agent-doc-policy-v1", "FULL");
        repository.markSuccess("task-rollback");
        repository.markValidationPassed("task-rollback", "digest-rollback", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
        Response switchAliasResponse = aliasResponse("agent-doc-policy-v1");
        Response switchUpdateResponse = mock(Response.class);
        when(switchRestClient.performRequest(any())).thenReturn(switchAliasResponse, switchUpdateResponse);
        service(switchRestClient, repository, auditRepository).switchReadAlias("agent-doc-policy", request());

        RestClient rollbackRestClient = mock(RestClient.class);
        Response rollbackAliasResponse = aliasResponse("agent-doc-policy-v2");
        Response rollbackUpdateResponse = mock(Response.class);
        when(rollbackRestClient.performRequest(any())).thenReturn(rollbackAliasResponse, rollbackUpdateResponse);
        AliasSwitchRequest request = request();
        request.setTaskId("task-rollback");
        request.setTargetIndex("agent-doc-policy-v1");
        request.setExpectedPreviousIndex("agent-doc-policy-v2");
        request.setValidationDigest("digest-rollback");

        service(rollbackRestClient, repository, auditRepository).rollbackReadAlias("agent-doc-policy", request);

        verify(rollbackRestClient, org.mockito.Mockito.times(2)).performRequest(any());
    }

    private EsIndexAliasService service() {
        return service(null, new InMemoryRebuildTaskRepository());
    }

    private EsIndexAliasService service(RestClient restClient, RebuildTaskRepository repository) {
        return service(restClient, repository, new InMemoryAliasOperationAuditRepository());
    }

    private EsIndexAliasService service(
            RestClient restClient,
            RebuildTaskRepository repository,
            AliasOperationAuditRepository auditRepository) {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        return new EsIndexAliasService(
                restClient,
                new ObjectMapper(),
                new DocumentIndexPolicy(properties),
                repository,
                auditRepository);
    }

    private RebuildTaskRepository validatedRepository(String taskId, String targetIndex, String digest) {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create(taskId, "agent-doc-policy", targetIndex, "FULL");
        repository.markSuccess(taskId);
        repository.markValidationPassed(taskId, digest, "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");
        return repository;
    }

    private Response aliasResponse(String currentIndex) throws Exception {
        Response response = mock(Response.class);
        HttpEntity entity = mock(HttpEntity.class);
        String body = "{\"" + currentIndex + "\":{\"aliases\":{\"agent-doc-policy\":{}}}}";
        when(entity.getContent()).thenReturn(new ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8)));
        when(response.getEntity()).thenReturn(entity);
        return response;
    }

    private AliasSwitchRequest request() {
        AliasSwitchRequest request = new AliasSwitchRequest();
        request.setTaskId("task-1");
        request.setTargetIndex("agent-doc-policy-v2");
        request.setExpectedPreviousIndex("agent-doc-policy-v1");
        request.setValidationDigest("digest-1");
        request.setOperatorRef("operator-1");
        request.setDomain("tax_policy");
        request.setMaterialType("policy");
        request.setProfileVersion("profile-v1");
        request.setIndexVersion("idx-v2");
        request.setGoldSetVersion("gold-tax-v1");
        request.setValidationReportId("report-v2");
        return request;
    }
}
