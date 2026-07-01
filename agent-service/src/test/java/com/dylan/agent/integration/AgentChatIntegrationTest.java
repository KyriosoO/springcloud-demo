package com.dylan.agent.integration;

import static org.hamcrest.Matchers.nullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.jwt;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Date;
import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.http.MediaType;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import com.dylan.agent.adapter.employee.EmployeeAgentClient;
import com.dylan.agent.adapter.transaction.TransactionAgentClient;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.ClarifySpec;
import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.conversation.ConversationHandle;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.conversation.TurnHandle;
import com.dylan.agent.exception.AgentRuntimeException;
import com.dylan.agent.persistence.mapper.AgentConversationMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchResponse;

@SpringBootTest(properties = {
        "spring.config.import=",
        "spring.cloud.config.enabled=false",
        "eureka.client.enabled=false"
})
@AutoConfigureMockMvc
@ActiveProfiles("test")
@DisplayName("AgentChatIntegrationTest")
class AgentChatIntegrationTest {

    @TestConfiguration
    static class MockRuntimeConfig {
        @Bean
        @Primary
        AgentRuntimeClient mockRuntimeClient() {
            return new AgentRuntimeClient(null, null, null) {
                @Override
                public PlanGenerateResponse generate(PlanGenerateRequest request) {
                    if (request.getMessage().contains("RUNTIME_FAIL")) {
                        throw new AgentRuntimeException("Runtime 不可用。");
                    }
                    PlanGenerateResponse response = new PlanGenerateResponse();
                    response.setRequestId(request.getRequestId());
                    response.setPlan(planFor(request.getMessage()));
                    return response;
                }

                private AgentPlan planFor(String message) {
                    AgentPlan plan = new AgentPlan();
                    plan.setPlanVersion(message.contains("INVALID_PLAN") ? "2.0" : "1.0");
                    boolean transaction = message.contains("TRANSACTION");
                    plan.setDomain(transaction ? "transaction" : "employee");
                    if (message.contains("CLARIFY")) {
                        plan.setIntent(AgentIntent.CLARIFY);
                        ClarifySpec clarify = new ClarifySpec();
                        clarify.setQuestion("请提供姓名、工号或岗位等查询条件。");
                        plan.setClarify(clarify);
                        return plan;
                    }

                    plan.setIntent(AgentIntent.QUERY);
                    AgentQuerySpec query = new AgentQuerySpec();
                    AgentFilter filter = new AgentFilter();
                    if (message.contains("TRANSACTION_INVALID")) {
                        filter.setField("position");
                        filter.setOperator(AgentOperator.EQ);
                        filter.setValue("HRM");
                        query.setSelectFields(List.of("transId"));
                    } else if (transaction) {
                        filter.setField("transType");
                        filter.setOperator(AgentOperator.CONTAINS);
                        filter.setValue("PAY");
                        query.setSelectFields(List.of("transId", "transType", "transDate", "amount"));
                    } else if (message.contains("PERM_DENY")) {
                        filter.setField("phoneNo");
                        filter.setOperator(AgentOperator.EQ);
                        filter.setValue("13812345678");
                        query.setSelectFields(List.of("chineseName", "phoneNo"));
                    } else {
                        filter.setField("position");
                        filter.setOperator(AgentOperator.EQ);
                        filter.setValue("HRM");
                        query.setSelectFields(List.of("chineseName", "memberNo", "position"));
                    }
                    query.setFilters(List.of(filter));
                    query.setPage(1);
                    query.setSize(20);
                    plan.setQuery(query);
                    return plan;
                }
            };
        }
    }

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private ConversationService conversationService;

    @MockitoBean
    private EmployeeAgentClient employeeAgentClient;

    @MockitoBean
    private TransactionAgentClient transactionAgentClient;

    @MockitoBean
    private AgentConversationMapper conversationMapper;

    @MockitoBean
    private AgentTurnMapper turnMapper;

    @BeforeEach
    void setUp() {
        when(conversationService.openConversation(any(), anyString()))
                .thenReturn(new ConversationHandle("conv-001"));
        when(conversationService.startTurn(anyString(), anyString(), anyString()))
                .thenReturn(new TurnHandle("turn-001"));
        when(conversationService.loadRecentTurns(anyString(), anyString(), anyInt()))
                .thenReturn(List.of());
        when(employeeAgentClient.search(any())).thenReturn("""
                {"hits":{"total":{"value":1,"relation":"eq"},"hits":[
                  {"_source":{"chineseName":"张三","memberNo":"E001","position":"HRM"}}
                ]}}
                """);
        Transaction row = new Transaction();
        row.setTransId("T10001");
        row.setTransType("PAYMENT");
        row.setTransDate(Date.from(Instant.parse("2026-06-22T00:00:00Z")));
        row.setAmount(new BigDecimal("128.50"));
        TransactionSearchResponse transactionResponse = new TransactionSearchResponse();
        transactionResponse.setRows(List.of(row));
        transactionResponse.setTotal(10000);
        transactionResponse.setTotalExact(false);
        transactionResponse.setPage(1);
        transactionResponse.setSize(20);
        when(transactionAgentClient.search(any())).thenReturn(transactionResponse);
    }

    @Nested
    @DisplayName("/agent/chat API")
    class ChatApi {

        @Test
        @DisplayName("QUERY 返回 RESULT 体")
        void shouldReturnQueryResult() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"查询岗位是HRM的员工，显示姓名、工号和岗位"}
                                    """))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.type").value("RESULT"))
                    .andExpect(jsonPath("$.conversationId").value("conv-001"))
                    .andExpect(jsonPath("$.turnId").value("turn-001"))
                    .andExpect(jsonPath("$.summary").isString())
                    .andExpect(jsonPath("$.result.resultKind").value("QUERY"))
                    .andExpect(jsonPath("$.result.queryParameters.domain").value("employee"))
                    .andExpect(jsonPath("$.result.queryParameters.filters[0].field").value("position"))
                    .andExpect(jsonPath("$.result.queryParameters.filters[0].operator").value("EQ"))
                    .andExpect(jsonPath("$.result.queryParameters.selectFields").isArray())
                    .andExpect(jsonPath("$.result.queryParameters.page").value(1))
                    .andExpect(jsonPath("$.result.queryParameters.size").value(20))
                    .andExpect(jsonPath("$.errorCode").value(nullValue()));
        }

        @Test
        @DisplayName("Transaction QUERY 返回完整 RESULT 体和下界总数")
        void shouldReturnTransactionQueryResult() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"TRANSACTION 查询交易类型包含 PAY 的交易"}
                                    """))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.type").value("RESULT"))
                    .andExpect(jsonPath("$.message").value("找到至少 10000 条记录。"))
                    .andExpect(jsonPath("$.result.resultKind").value("QUERY"))
                    .andExpect(jsonPath("$.result.queryParameters.domain").value("transaction"))
                    .andExpect(jsonPath("$.result.queryParameters.filters[0].field").value("transType"))
                    .andExpect(jsonPath("$.result.queryResult.columns[0]").value("transId"))
                    .andExpect(jsonPath("$.result.queryResult.rows[0].transId").value("T10001"))
                    .andExpect(jsonPath("$.result.queryResult.rows[0].transType").value("PAYMENT"))
                    .andExpect(jsonPath("$.result.queryResult.rows[0].transDate")
                            .value("2026-06-22T00:00:00Z"))
                    .andExpect(jsonPath("$.result.queryResult.rows[0].amount").value(128.50))
                    .andExpect(jsonPath("$.result.queryResult.total").value(10000))
                    .andExpect(jsonPath("$.result.queryResult.totalExact").value(false))
                    .andExpect(jsonPath("$.result.queryResult.page").value(1))
                    .andExpect(jsonPath("$.result.queryResult.size").value(20));
        }

        @Test
        @DisplayName("Transaction 非法跨域字段在调用 Feign 前拒绝")
        void shouldRejectInvalidTransactionFieldBeforeFeign() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"TRANSACTION_INVALID"}
                                    """))
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.errorCode").value("AGENT_PLAN_INVALID"));

            verifyNoInteractions(transactionAgentClient);
        }

        @Test
        @DisplayName("CLARIFY 返回反问消息")
        void shouldReturnClarify() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"CLARIFY 帮查员工"}
                                    """))
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.type").value("CLARIFY"))
                    .andExpect(jsonPath("$.message").isString())
                    .andExpect(jsonPath("$.summary").isString())
                    .andExpect(jsonPath("$.result").value(nullValue()));
        }

        @Test
        @DisplayName("viewer 查询敏感字段返回 403 ERROR")
        void shouldReturn403ForViewerQueryingSensitiveField() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(viewerJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"PERM_DENY 查询手机号"}
                                    """))
                    .andExpect(status().isForbidden())
                    .andExpect(jsonPath("$.type").value("ERROR"))
                    .andExpect(jsonPath("$.errorCode").value("AGENT_FIELD_FORBIDDEN"));
        }

        @Test
        @DisplayName("非法 Plan 返回 422 ERROR")
        void shouldReturn422ForInvalidPlan() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"INVALID_PLAN"}
                                    """))
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.type").value("ERROR"))
                    .andExpect(jsonPath("$.errorCode").value("AGENT_PLAN_INVALID"));
        }

        @Test
        @DisplayName("Runtime 失败返回 502 ERROR")
        void shouldReturn502ForRuntimeFailure() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"RUNTIME_FAIL"}
                                    """))
                    .andExpect(status().isBadGateway())
                    .andExpect(jsonPath("$.type").value("ERROR"))
                    .andExpect(jsonPath("$.errorCode").value("AGENT_RUNTIME_UNAVAILABLE"));
        }

        @Test
        @DisplayName("缺少 message 返回 400")
        void shouldReturn400ForMissingMessage() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .with(adminJwt())
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":""}
                                    """))
                    .andExpect(status().isBadRequest());
        }

        @Test
        @DisplayName("无 Token 返回 401")
        void shouldReturn401ForMissingToken() throws Exception {
            mockMvc.perform(post("/agent/chat")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content("""
                                    {"message":"test"}
                                    """))
                    .andExpect(status().isUnauthorized());
        }
    }

    @Nested
    @DisplayName("/agent.html 页面")
    class StaticPage {

        @Test
        @DisplayName("认证后可访问 agent.html 页面")
        void shouldServeAgentPage() throws Exception {
            mockMvc.perform(get("/agent.html").with(adminJwt()))
                    .andExpect(status().isOk());
        }
    }

    private static org.springframework.test.web.servlet.request.RequestPostProcessor adminJwt() {
        return jwt().jwt(token -> token.subject("admin")
                .claim("role", List.of("agent:admin", "agent:viewer")));
    }

    private static org.springframework.test.web.servlet.request.RequestPostProcessor viewerJwt() {
        return jwt().jwt(token -> token.subject("viewer_t")
                .claim("role", List.of("agent:viewer")));
    }
}
