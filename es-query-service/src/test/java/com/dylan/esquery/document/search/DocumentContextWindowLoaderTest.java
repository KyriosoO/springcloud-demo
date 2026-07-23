package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.DocumentSearchChannel;
import com.dylan.esquery.api.model.document.DocumentChannelRank;
import com.dylan.esquery.api.model.document.HybridContextRequest;
import com.dylan.esquery.api.model.document.HybridSearchHit;
import com.dylan.esquery.security.DocumentProtectedFilterCompiler;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.HttpEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.io.ByteArrayInputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class DocumentContextWindowLoaderTest {
    @Test
    void loadsAllNeighborsInOneFilteredBatchAndAppliesGlobalCodePointBudget() throws Exception {
        RestClient client = mock(RestClient.class);
        Response contextResponse = response("""
                {"hits":{"hits":[
                  {"_score":1.0,"_source":{"documentId":"doc-1","documentVersion":"v1","chunkId":"c-0","chunkIndex":0,"aclRef":"acl-1","aclVersion":"v1","tenantId":"tenant-1","status":"ACTIVE","content":"上文甲乙"}},
                  {"_score":1.0,"_source":{"documentId":"doc-1","documentVersion":"v1","chunkId":"c-2","chunkIndex":2,"aclRef":"acl-1","aclVersion":"v1","tenantId":"tenant-1","status":"ACTIVE","content":"下文丙丁"}}
                ]}}
                """);
        when(client.performRequest(any(Request.class))).thenReturn(contextResponse);
        ObjectMapper mapper = new ObjectMapper();
        Clock clock = Clock.systemUTC();
        var executors = new DocumentChannelExecutorRegistry(
                client, mapper, new DocumentProtectedFilterCompiler(), clock);
        var loader = new DocumentContextWindowLoader(client, mapper, executors, clock);

        var result = loader.loadBatch(List.of(anchor()),
                DocumentSearchTestFixtures.request(new HybridContextRequest(1, 1, 6)),
                DocumentSearchTestFixtures.target(), DocumentSearchTestFixtures.corpus());

        assertThat(result.hits()).singleElement().satisfies(hit -> {
            assertThat(hit.contextBefore()).containsExactly("上文甲乙");
            assertThat(hit.contextAfter()).containsExactly("下文");
        });
        assertThat(result.truncated()).isTrue();
        ArgumentCaptor<Request> request = ArgumentCaptor.forClass(Request.class);
        verify(client, times(1)).performRequest(request.capture());
        String body = new String(request.getValue().getEntity().getContent().readAllBytes(), StandardCharsets.UTF_8);
        assertThat(body).contains("tenantId", "documentVersion", "chunkIndex", "doc-1");
    }

    private static HybridSearchHit anchor() {
        return new HybridSearchHit("candidate-1", "doc-1", "v1", "c-1", 1, "acl-1", "v1",
                "政策", "policy", null, null, null, "命中", "正文", null, null,
                List.of(), List.of(), null, null, BigDecimal.ONE, BigDecimal.ONE,
                List.of(new DocumentChannelRank(DocumentSearchChannel.BM25, 1, BigDecimal.ONE)));
    }

    private static Response response(String json) throws Exception {
        Response response = mock(Response.class);
        HttpEntity entity = mock(HttpEntity.class);
        when(entity.getContent()).thenReturn(new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8)));
        when(response.getEntity()).thenReturn(entity);
        return response;
    }
}
