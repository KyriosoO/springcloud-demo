package com.dylan.agent.capability.document.embedding;

import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import com.dylan.common.security.ServiceTokenProvider;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withStatus;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class HttpDocumentEmbeddingClientTest {

    @Test
    void sendsProviderHeadersAndBody() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://embedding-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        Instant deadline = Instant.now().plusSeconds(60);
        server.expect(requestTo("http://embedding-provider/embeddings"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer service-token"))
                .andExpect(header("X-Agent-Request-Id", "inv-1"))
                .andExpect(header("X-Agent-Deadline", deadline.toString()))
                .andExpect(jsonPath("$.requestId").value("inv-1"))
                .andExpect(jsonPath("$.input").value("查询休假政策"))
                .andExpect(jsonPath("$.queryVariants[0]").value("查询休假政策"))
                .andExpect(jsonPath("$.queryVariants[1]").value("休假审批政策"))
                .andExpect(jsonPath("$.domain").value("policy_document"))
                .andExpect(jsonPath("$.provider").value("bge"))
                .andExpect(jsonPath("$.model").value("embedding-v1"))
                .andExpect(jsonPath("$.expectedModel").value("embedding-v1"))
                .andExpect(jsonPath("$.expectedDimension").value(2))
                .andExpect(jsonPath("$.aclScope").doesNotExist())
                .andExpect(jsonPath("$.indexAlias").doesNotExist())
                .andExpect(jsonPath("$.deadline").value(deadline.toString()))
                .andRespond(withSuccess("""
                        {"queryVector":[0.1,0.2],"embeddingModel":"embedding-v1","dimension":2,"digest":"vec-digest"}
                        """, MediaType.APPLICATION_JSON));
        var client = new HttpDocumentEmbeddingClient(builder.build(), authHeaderProvider("service-token"));

        DocumentEmbeddingResult result = client.embed(new DocumentEmbeddingRequest(
                "inv-1",
                "查询休假政策",
                List.of("查询休假政策", "休假审批政策"),
                "policy_document",
                "bge",
                "embedding-v1",
                "embedding-v1",
                2,
                deadline));

        assertThat(result.queryVector()).containsExactly(0.1, 0.2);
        assertThat(result.embeddingModel()).isEqualTo("embedding-v1");
        assertThat(result.dimension()).isEqualTo(2);
        assertThat(result.digest()).isEqualTo("vec-digest");
        server.verify();
    }

    @Test
    void wrapsProviderFailureWithoutSensitiveBodyOrToken() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://embedding-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("http://embedding-provider/embeddings"))
                .andRespond(withServerError().body("raw-body-with-secret-token-and-queryVector"));
        var client = new HttpDocumentEmbeddingClient(builder.build(), authHeaderProvider("service-token"));

        assertThatThrownBy(() -> client.embed(new DocumentEmbeddingRequest(
                "inv-1",
                "敏感查询文本",
                "policy_document",
                "embedding-v1",
                Instant.now().plusSeconds(60))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document embedding provider call failed")
                .hasNoCause()
                .hasMessageNotContaining("service-token")
                .hasMessageNotContaining("敏感查询文本")
                .hasMessageNotContaining("raw-body");
        server.verify();
    }

    @Test
    void fallsBackToLocalEmbedEndpointWhenEmbeddingsPathIsMissing() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://embedding-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        Instant deadline = Instant.now().plusSeconds(60);
        server.expect(requestTo("http://embedding-provider/embeddings"))
                .andRespond(withStatus(HttpStatus.NOT_FOUND));
        server.expect(requestTo("http://embedding-provider/embed"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer service-token"))
                .andExpect(jsonPath("$.texts[0]").value("查询休假政策"))
                .andExpect(jsonPath("$.texts[1]").value("休假审批政策"))
                .andRespond(withSuccess("""
                        {"dim":2,"vectors":[[1.0,0.0],[0.0,1.0]]}
                        """, MediaType.APPLICATION_JSON));
        var client = new HttpDocumentEmbeddingClient(builder.build(), authHeaderProvider("service-token"));

        DocumentEmbeddingResult result = client.embed(new DocumentEmbeddingRequest(
                "inv-1",
                "查询休假政策",
                List.of("查询休假政策", "休假审批政策"),
                "policy_document",
                "bge",
                "embedding-v1",
                "embedding-v1",
                2,
                deadline));

        assertThat(result.queryVector()).containsExactly(0.5, 0.5);
        assertThat(result.embeddingModel()).isEqualTo("embedding-v1");
        assertThat(result.dimension()).isEqualTo(2);
        server.verify();
    }

    @Test
    void rejectsNonFiniteVector() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://embedding-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("http://embedding-provider/embeddings"))
                .andRespond(withSuccess("""
                        {"queryVector":["bad"],"embeddingModel":"embedding-v1","dimension":1}
                        """, MediaType.APPLICATION_JSON));
        var client = new HttpDocumentEmbeddingClient(builder.build(), authHeaderProvider("service-token"));

        assertThatThrownBy(() -> client.embed(new DocumentEmbeddingRequest(
                "inv-1",
                "查询休假政策",
                "policy_document",
                "embedding-v1",
                Instant.now().plusSeconds(60))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document embedding provider call failed")
                .hasNoCause();
        server.verify();
    }

    @Test
    void rejectsDimsMismatch() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://embedding-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("http://embedding-provider/embeddings"))
                .andRespond(withSuccess("""
                        {"queryVector":[0.1],"embeddingModel":"embedding-v1","dimension":1}
                        """, MediaType.APPLICATION_JSON));
        var client = new HttpDocumentEmbeddingClient(builder.build(), authHeaderProvider("service-token"));

        assertThatThrownBy(() -> client.embed(new DocumentEmbeddingRequest(
                "inv-1",
                "查询休假政策",
                List.of("查询休假政策"),
                "policy_document",
                "bge",
                "embedding-v1",
                "embedding-v1",
                2,
                Instant.now().plusSeconds(60))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document embedding provider call failed")
                .hasNoCause();
        server.verify();
    }

    private DocumentProviderAuthHeaderProvider authHeaderProvider(String token) {
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn(token);
        return new DocumentProviderAuthHeaderProvider(tokenProvider);
    }
}
