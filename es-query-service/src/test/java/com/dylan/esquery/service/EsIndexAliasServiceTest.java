package com.dylan.esquery.service;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class EsIndexAliasServiceTest {

    @Test
    void authorizedCommandRejectsGenericAliasTargets() {
        assertThatThrownBy(() -> new EsIndexAliasService.AuthorizedAliasChangeCommand(
                "change-1", new DocumentCorpusKeyDto("policy", "document"), "orders-read", List.of(), "orders-v2",
                "a".repeat(64), "report-1", "b".repeat(64), "c".repeat(64), Instant.now().plusSeconds(60)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("document alias");
    }

    @Test
    void compareAndSwitchFailsClosedWhenExpectedTargetIsStale() throws Exception {
        RestClient client = mock(RestClient.class);
        Response current = response("{\"agent-doc-policy-v1\":{}}");
        when(client.performRequest(any(Request.class)))
                .thenReturn(current);
        EsIndexAliasService service = new EsIndexAliasService(client, new ObjectMapper());

        var result = service.compareAndSwitch(command(List.of("agent-doc-policy-v0")));

        assertThat(result).isEqualTo(EsIndexAliasService.AliasChangeResult.CONFLICT);
        verify(client, times(1)).performRequest(any(Request.class));
    }

    @Test
    void compareAndSwitchVerifiesActualAliasAfterOneAtomicMutation() throws Exception {
        RestClient client = mock(RestClient.class);
        Response before = response("{\"agent-doc-policy-v1\":{}}");
        Response mapping = response("{\"agent-doc-policy-v2\":{\"mappings\":{\"_meta\":{\"agent_document_manifest\":{" +
                "\"sealed\":true,\"domain\":\"policy\",\"materialType\":\"document\"," +
                "\"manifestDigest\":\"" + "a".repeat(64) + "\",\"validationReportRef\":\"report-1\"," +
                "\"attestationDigest\":\"" + "b".repeat(64) + "\"}}}}}");
        Response settings = response("{\"agent-doc-policy-v2\":{\"settings\":{\"index.blocks.write\":\"true\"}}}");
        Response mutation = mock(Response.class);
        Response after = response("{\"agent-doc-policy-v2\":{}}");
        when(client.performRequest(any(Request.class))).thenReturn(
                before, mapping, settings, mutation, after);
        EsIndexAliasService service = new EsIndexAliasService(client, new ObjectMapper());

        var result = service.compareAndSwitch(command(List.of("agent-doc-policy-v1")));

        assertThat(result).isEqualTo(EsIndexAliasService.AliasChangeResult.APPLIED);
        ArgumentCaptor<Request> requests = ArgumentCaptor.forClass(Request.class);
        verify(client, times(5)).performRequest(requests.capture());
        assertThat(requests.getAllValues()).extracting(Request::getMethod)
                .containsExactly("GET", "GET", "GET", "POST", "GET");
        assertThat(requests.getAllValues().get(3).getEndpoint()).isEqualTo("/_aliases");
    }

    private static EsIndexAliasService.AuthorizedAliasChangeCommand command(List<String> expected) {
        return new EsIndexAliasService.AuthorizedAliasChangeCommand("change-1",
                new DocumentCorpusKeyDto("policy", "document"), "agent-doc-policy-read", expected,
                "agent-doc-policy-v2", "a".repeat(64), "report-1", "b".repeat(64),
                "c".repeat(64), Instant.now().plusSeconds(60));
    }

    private static Response response(String body) {
        Response response = mock(Response.class);
        when(response.getEntity()).thenReturn(new NStringEntity(body, ContentType.APPLICATION_JSON));
        return response;
    }
}
