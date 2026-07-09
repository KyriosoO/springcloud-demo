package com.dylan.agent.capability.document.rerank;

import com.dylan.agent.adapter.api.document.AdapterDocumentEvidence;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import com.dylan.common.security.ServiceTokenProvider;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class HttpDocumentRerankClientTest {

    @Test
    void sendsSafeCandidatesAndMapsRerankScores() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://rerank-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        Instant deadline = Instant.now().plusSeconds(60);
        server.expect(requestTo("http://rerank-provider/rerank"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer service-token"))
                .andExpect(header("X-Agent-Request-Id", "inv-1"))
                .andExpect(header("X-Agent-Deadline", deadline.toString()))
                .andExpect(jsonPath("$.query").value("增值税税率"))
                .andExpect(jsonPath("$.documents[0]").value(containsString("标题：增值税政策")))
                .andExpect(jsonPath("$.documents[0]").value(containsString("摘要：税率说明")))
                .andExpect(jsonPath("$.documents[0]").value(not(containsString("完整正文"))))
                .andExpect(jsonPath("$.top_n").value(2))
                .andExpect(jsonPath("$.normalize").value(true))
                .andRespond(withSuccess("""
                        {"model":"BAAI/bge-reranker-v2-m3","results":[
                          {"index":1,"text":"小规模纳税人政策","score":0.91},
                          {"index":0,"text":"增值税政策","score":0.73}
                        ]}
                        """, MediaType.APPLICATION_JSON));
        var client = new HttpDocumentRerankClient(
                builder.build(),
                authHeaderProvider("service-token"),
                "/rerank",
                "BAAI/bge-reranker-v2-m3",
                true,
                1200);

        AdapterDocumentResult result = client.rerank(new DocumentRerankRequest(
                "inv-1",
                "tax_policy",
                "tax_policy",
                "tax_policy_v2_default",
                "增值税税率",
                2,
                candidates(),
                deadline));

        assertThat(result.getHits()).hasSize(2);
        assertThat(result.getHits().get(0).getChunkId()).isEqualTo("chunk-2");
        assertThat(result.getHits().get(0).getScore()).isEqualByComparingTo("0.91");
        assertThat(result.getHits().get(0).getMetadata())
                .containsEntry("rerankScore", 0.91d)
                .containsEntry("rerankReasonCode", "BAAI/bge-reranker-v2-m3");
        assertThat(result.getHits().get(1).getChunkId()).isEqualTo("chunk-1");
        server.verify();
    }

    @Test
    void wrapsProviderFailureWithoutSensitiveBody() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://rerank-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("http://rerank-provider/rerank"))
                .andRespond(withServerError().body("raw-body-with-query-and-token"));
        var client = new HttpDocumentRerankClient(
                builder.build(),
                authHeaderProvider("service-token"),
                "/rerank",
                "BAAI/bge-reranker-v2-m3",
                true,
                1200);

        assertThatThrownBy(() -> client.rerank(new DocumentRerankRequest(
                "inv-1",
                "tax_policy",
                "tax_policy",
                "tax_policy_v2_default",
                "敏感查询",
                2,
                candidates(),
                Instant.now().plusSeconds(60))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document rerank provider call failed")
                .hasNoCause()
                .hasMessageNotContaining("敏感查询")
                .hasMessageNotContaining("service-token")
                .hasMessageNotContaining("raw-body");
        server.verify();
    }

    private AdapterDocumentResult candidates() {
        AdapterDocumentResult result = new AdapterDocumentResult();
        result.setHits(List.of(
                evidence("chunk-1", "增值税政策", "税率说明", "完整正文不应发送"),
                evidence("chunk-2", "小规模纳税人政策", "优惠说明", "完整正文不应发送")));
        return result;
    }

    private AdapterDocumentEvidence evidence(String chunkId, String title, String snippet, String content) {
        AdapterDocumentEvidence evidence = new AdapterDocumentEvidence();
        evidence.setDocumentId("doc-" + chunkId);
        evidence.setChunkId(chunkId);
        evidence.setTitle(title);
        evidence.setSection("正文");
        evidence.setSnippet(snippet);
        evidence.setContent(content);
        evidence.setMetadata(Map.of("documentNo", "税务公告2026年第1号"));
        return evidence;
    }

    private DocumentProviderAuthHeaderProvider authHeaderProvider(String token) {
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn(token);
        return new DocumentProviderAuthHeaderProvider(tokenProvider);
    }
}
