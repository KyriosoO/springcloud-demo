package com.dylan.agent.capability.document.generation;

import com.dylan.agent.api.plan.DocumentPlanOperation;
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
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class HttpDocumentGenerationClientTest {

    @Test
    void sendsProviderHeadersAndBody() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://generation-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        Instant deadline = Instant.now().plusSeconds(60);
        server.expect(requestTo("http://generation-provider/document-generation"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer service-token"))
                .andExpect(header("X-Agent-Request-Id", "inv-1"))
                .andExpect(header("X-Agent-Deadline", deadline.toString()))
                .andExpect(jsonPath("$.requestId").value("inv-1"))
                .andExpect(jsonPath("$.operation").value("ANSWER"))
                .andExpect(jsonPath("$.queryText").value("查询休假政策"))
                .andExpect(jsonPath("$.model").value("generation-v1"))
                .andExpect(jsonPath("$.contextPackage.digest").value("ctx-digest"))
                .andExpect(jsonPath("$.maxOutputChars").value(2000))
                .andExpect(jsonPath("$.deadline").value(deadline.toString()))
                .andRespond(withSuccess("""
                        {
                          "answerText":"员工年假需要直属主管审批。[chunk-1]",
                          "summaryText":null,
                          "summaryBullets":null,
                          "citationBindings":[{"text":"员工年假需要直属主管审批。","citationIds":["chunk-1"]}],
                          "finishReason":"stop"
                        }
                        """, MediaType.APPLICATION_JSON));
        var client = new HttpDocumentGenerationClient(builder.build(), authHeaderProvider("service-token"));

        DocumentGenerationResult result = client.generate(new DocumentGenerationRequest(
                "inv-1",
                DocumentPlanOperation.ANSWER,
                "查询休假政策",
                "generation-v1",
                contextPackage(deadline),
                2000,
                deadline));

        assertThat(result.answerText()).contains("员工年假");
        assertThat(result.citationBindings()).singleElement()
                .extracting(CitationBinding::citationIds)
                .isEqualTo(List.of("chunk-1"));
        server.verify();
    }

    @Test
    void wrapsProviderFailureWithoutSensitiveBodyOrToken() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://generation-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("http://generation-provider/document-generation"))
                .andRespond(withServerError().body("raw-answer-with-service-token-and-evidence"));
        var client = new HttpDocumentGenerationClient(builder.build(), authHeaderProvider("service-token"));
        Instant deadline = Instant.now().plusSeconds(60);

        assertThatThrownBy(() -> client.generate(new DocumentGenerationRequest(
                "inv-1",
                DocumentPlanOperation.ANSWER,
                "敏感查询文本",
                "generation-v1",
                contextPackage(deadline),
                2000,
                deadline)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document generation provider call failed")
                .hasNoCause()
                .hasMessageNotContaining("service-token")
                .hasMessageNotContaining("敏感查询文本")
                .hasMessageNotContaining("raw-answer");
        server.verify();
    }

    @Test
    void rejectsExpiredDeadlineBeforeHttpCall() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://generation-provider");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        var client = new HttpDocumentGenerationClient(builder.build(), authHeaderProvider("service-token"));
        Instant deadline = Instant.now().minusSeconds(1);

        assertThatThrownBy(() -> client.generate(new DocumentGenerationRequest(
                "inv-1",
                DocumentPlanOperation.ANSWER,
                "查询休假政策",
                "generation-v1",
                contextPackage(deadline),
                2000,
                deadline)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document generation provider call failed")
                .hasNoCause();
        server.verify();
    }

    private EvidenceContextPackage contextPackage(Instant deadline) {
        return new EvidenceContextPackage(
                "inv-1",
                DocumentPlanOperation.ANSWER,
                "查询休假政策",
                List.of(new DocumentEvidenceContextItem(
                        "chunk-1",
                        "员工年假需要直属主管审批。",
                        Map.of("sourceType", "policy"))),
                Set.of("chunk-1"),
                new DocumentContextBudget(8000, 1200, 8, 2000),
                "ctx-digest");
    }

    private DocumentProviderAuthHeaderProvider authHeaderProvider(String token) {
        ServiceTokenProvider tokenProvider = mock(ServiceTokenProvider.class);
        when(tokenProvider.token()).thenReturn(token);
        return new DocumentProviderAuthHeaderProvider(tokenProvider);
    }
}
