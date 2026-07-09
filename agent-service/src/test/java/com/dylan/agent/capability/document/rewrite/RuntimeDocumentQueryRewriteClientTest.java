package com.dylan.agent.capability.document.rewrite;

import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class RuntimeDocumentQueryRewriteClientTest {

    @Test
    void sendsOnlyMinimalRewriteRequestFields() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://runtime");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        AgentProperties properties = properties();
        server.expect(requestTo("http://runtime/runtime/v1/document/rewrite"))
                .andExpect(header("X-Agent-Runtime-Key", properties.getRuntime().getSharedKey()))
                .andExpect(header("X-Agent-Request-Id", "inv-1"))
                .andExpect(jsonPath("$.requestId").value("inv-1"))
                .andExpect(jsonPath("$.query").value("查询增值税优惠"))
                .andExpect(jsonPath("$.domain").value("policy_document"))
                .andExpect(jsonPath("$.materialType").value("tax_policy"))
                .andExpect(jsonPath("$.language").value("zh-CN"))
                .andExpect(jsonPath("$.maxCandidates").value(2))
                .andExpect(jsonPath("$.indexAlias").doesNotExist())
                .andExpect(jsonPath("$.retrievalProfile").doesNotExist())
                .andExpect(jsonPath("$.aclScope").doesNotExist())
                .andRespond(withSuccess("""
                        {"candidates":[{"text":"小规模纳税人增值税优惠","intentLabel":"tax","confidence":0.9}],"diagnosticId":"rw-1","model":"test"}
                        """, MediaType.APPLICATION_JSON));
        var client = new RuntimeDocumentQueryRewriteClient(builder.build(), new ObjectMapper(), properties);

        DocumentRewriteResponse response = client.rewrite(new DocumentRewriteRequest(
                "inv-1",
                "查询增值税优惠",
                "policy_document",
                "tax_policy",
                "zh-CN",
                2,
                1000,
                Instant.now().plusSeconds(60)));

        assertThat(response.candidates()).singleElement()
                .extracting(DocumentRewriteCandidate::text)
                .isEqualTo("小规模纳税人增值税优惠");
        assertThat(response.diagnosticId()).isEqualTo("rw-1");
        server.verify();
    }

    @Test
    void rejectsForbiddenFieldsFromRuntimeResponse() {
        RestClient.Builder builder = RestClient.builder().baseUrl("http://runtime");
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        AgentProperties properties = properties();
        server.expect(requestTo("http://runtime/runtime/v1/document/rewrite"))
                .andRespond(withSuccess("""
                        {"candidates":[{"text":"x","filter":{"tenantId":"t1"}}],"diagnosticId":"rw-2"}
                        """, MediaType.APPLICATION_JSON));
        var client = new RuntimeDocumentQueryRewriteClient(builder.build(), new ObjectMapper(), properties);

        assertThatThrownBy(() -> client.rewrite(new DocumentRewriteRequest(
                "inv-1",
                "查询增值税优惠",
                "policy_document",
                "tax_policy",
                "zh-CN",
                2,
                1000,
                Instant.now().plusSeconds(60))))
                .isInstanceOf(IllegalStateException.class)
                .hasMessage("document rewrite provider call failed");
        server.verify();
    }

    private AgentProperties properties() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRewrite().setEnabled(true);
        properties.getDocument().getRewrite().setPath("/runtime/v1/document/rewrite");
        return properties;
    }
}
