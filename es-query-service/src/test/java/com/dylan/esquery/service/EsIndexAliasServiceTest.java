package com.dylan.esquery.service;

import com.dylan.esquery.api.model.AliasSwitchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.StatusLine;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;

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
        RebuildTaskRepository repository = new RebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("validation must be PASSED");
    }

    @Test
    void rejectsAliasSwitchWhenValidationDigestDoesNotMatchTask() {
        RebuildTaskRepository repository = new RebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");
        repository.markValidationPassed("task-1", "real-digest", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");

        assertThatThrownBy(() -> service(null, repository).switchReadAlias("agent-doc-policy", request()))
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
        RebuildTaskRepository repository = new RebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markSuccess("task-1");
        repository.markValidationPassed("task-1", "digest-1", "LOCAL_DOCUMENT_INDEX_VALIDATION_V1");

        assertThatThrownBy(() -> service(restClient, repository).switchReadAlias("agent-doc-policy", request()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("expectedPreviousIndex");
        verify(restClient).performRequest(any());
    }

    private EsIndexAliasService service() {
        return service(null, new RebuildTaskRepository());
    }

    private EsIndexAliasService service(RestClient restClient, RebuildTaskRepository repository) {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        return new EsIndexAliasService(
                restClient,
                new ObjectMapper(),
                new DocumentIndexPolicy(properties),
                repository);
    }

    private AliasSwitchRequest request() {
        AliasSwitchRequest request = new AliasSwitchRequest();
        request.setTaskId("task-1");
        request.setTargetIndex("agent-doc-policy-v2");
        request.setExpectedPreviousIndex("agent-doc-policy-v1");
        request.setValidationDigest("digest-1");
        request.setOperatorRef("operator-1");
        return request;
    }
}
