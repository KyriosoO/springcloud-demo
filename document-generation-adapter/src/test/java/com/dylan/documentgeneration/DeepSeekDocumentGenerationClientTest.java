package com.dylan.documentgeneration;

import com.dylan.documentgeneration.model.DocumentContextBudget;
import com.dylan.documentgeneration.model.DocumentEvidenceContextItem;
import com.dylan.documentgeneration.model.DocumentGenerationRequest;
import com.dylan.documentgeneration.model.DocumentPlanOperation;
import com.dylan.documentgeneration.model.EvidenceContextPackage;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class DeepSeekDocumentGenerationClientTest {

    @Test
    void convertsDeepSeekChatCompletionToDocumentGenerationResult() {
        RestClient.Builder builder = RestClient.builder().baseUrl("https://api.deepseek.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        DeepSeekGenerationProperties properties = properties();
        server.expect(requestTo("https://api.deepseek.test/v1/chat/completions"))
                .andExpect(header(HttpHeaders.AUTHORIZATION, "Bearer test-key"))
                .andExpect(jsonPath("$.model").value("deepseek-test"))
                .andExpect(jsonPath("$.messages[1].content").value(org.hamcrest.Matchers.containsString("[chunk-1]")))
                .andRespond(withSuccess("""
                        {
                          "choices": [{
                            "message": {
                              "content": "{\\"answerText\\":\\"当前增值税税率包括13%、9%、6%等档次。[chunk-1]\\",\\"summaryText\\":null,\\"summaryBullets\\":null,\\"citationBindings\\":[{\\"text\\":\\"当前增值税税率包括13%、9%、6%等档次。\\",\\"citationIds\\":[\\"chunk-1\\",\\"fake\\"]}],\\"finishReason\\":\\"stop\\"}"
                            }
                          }]
                        }
                        """, MediaType.APPLICATION_JSON));
        var client = new DeepSeekDocumentGenerationClient(builder.build(), properties, new ObjectMapper());

        var result = client.generate(request());

        assertThat(result.answerText()).contains("13%");
        assertThat(result.citationBindings()).singleElement().satisfies(binding -> {
            assertThat(binding.citationIds()).containsExactly("chunk-1");
        });
        server.verify();
    }

    @Test
    void derivesCitationBindingsWhenModelOmitsBindingsButUsesCitationMarkers() {
        RestClient.Builder builder = RestClient.builder().baseUrl("https://api.deepseek.test");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        server.expect(requestTo("https://api.deepseek.test/v1/chat/completions"))
                .andRespond(withSuccess("""
                        {
                          "choices": [{
                            "message": {
                              "content": "{\\"answerText\\":\\"税率信息见法条。[chunk-1]\\",\\"summaryText\\":null,\\"summaryBullets\\":null,\\"citationBindings\\":[],\\"finishReason\\":\\"stop\\"}"
                            }
                          }]
                        }
                        """, MediaType.APPLICATION_JSON));
        var client = new DeepSeekDocumentGenerationClient(builder.build(), properties(), new ObjectMapper());

        var result = client.generate(request());

        assertThat(result.citationBindings()).singleElement()
                .extracting(binding -> binding.citationIds())
                .isEqualTo(List.of("chunk-1"));
        server.verify();
    }

    private DeepSeekGenerationProperties properties() {
        DeepSeekGenerationProperties properties = new DeepSeekGenerationProperties();
        properties.setBaseUrl("https://api.deepseek.test");
        properties.setApiKey("test-key");
        properties.setModel("deepseek-test");
        return properties;
    }

    private DocumentGenerationRequest request() {
        Instant deadline = Instant.now().plusSeconds(60);
        return new DocumentGenerationRequest(
                "inv-1",
                DocumentPlanOperation.ANSWER,
                "当前增值税税率有哪几档？",
                "deepseek-test",
                new EvidenceContextPackage(
                        "inv-1",
                        DocumentPlanOperation.ANSWER,
                        "当前增值税税率有哪几档？",
                        List.of(new DocumentEvidenceContextItem(
                                "chunk-1",
                                "增值税税率包括13%、9%、6%。",
                                Map.of("title", "中华人民共和国增值税法"))),
                        Set.of("chunk-1"),
                        new DocumentContextBudget(8000, 1200, 8, 2000),
                        "digest"),
                2000,
                deadline);
    }
}
