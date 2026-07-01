package com.dylan.agent.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.RuntimeRole;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Agent API 契约 JSON 反序列化测试。
 * 使用 golden fixture 验证 Java 与 Python 共用契约。
 */
class AgentContractJsonTest {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);

    @Nested
    @DisplayName("QUERY Plan 反序列化")
    class QueryPlanTest {

        @Test
        @DisplayName("从 golden fixture 正确解析 QUERY Plan")
        void shouldParseQueryPlanFromFixture() throws Exception {
            PlanGenerateResponse response = readFixture("contracts/query-plan-v1.json");

            assertThat(response.getRequestId()).isEqualTo("turn-001");
            AgentPlan plan = response.getPlan();
            assertThat(plan.getPlanVersion()).isEqualTo("1.0");
            assertThat(plan.getIntent()).isEqualTo(AgentIntent.QUERY);
            assertThat(plan.getDomain()).isEqualTo("employee");
            assertThat(plan.getQuery()).isNotNull();
            assertThat(plan.getClarify()).isNull();
            assertThat(plan.getQuery().getFilters()).hasSize(1);
            assertThat(plan.getQuery().getFilters().get(0).getField()).isEqualTo("position");
            assertThat(plan.getQuery().getFilters().get(0).getOperator()).isEqualTo(AgentOperator.EQ);
            assertThat(plan.getQuery().getFilters().get(0).getValue()).isEqualTo("HRM");
            assertThat(plan.getQuery().getSelectFields()).containsExactly("chineseName", "memberNo", "position");
            assertThat(plan.getQuery().getPage()).isEqualTo(1);
            assertThat(plan.getQuery().getSize()).isEqualTo(20);
        }
    }

    @Nested
    @DisplayName("AGGREGATE Plan 反序列化")
    class AggregatePlanTest {

        @Test
        @DisplayName("从 golden fixture 正确解析 AGGREGATE Plan")
        void shouldParseAggregatePlanFromFixture() throws Exception {
            PlanGenerateResponse response = readFixture("contracts/aggregate-plan-v1.json");

            assertThat(response.getRequestId()).isEqualTo("turn-001");
            AgentPlan plan = response.getPlan();
            assertThat(plan.getPlanVersion()).isEqualTo("1.0");
            assertThat(plan.getIntent()).isEqualTo(AgentIntent.AGGREGATE);
            assertThat(plan.getDomain()).isEqualTo("transaction");
            assertThat(plan.getQuery()).isNull();
            assertThat(plan.getClarify()).isNull();
            assertThat(plan.getAggregate()).isNotNull();
            assertThat(plan.getAggregate().getMetrics()).hasSize(2);
            assertThat(plan.getAggregate().getMetrics().get(0).getFunction())
                    .isEqualTo(AggregateFunction.SUM);
            assertThat(plan.getAggregate().getMetrics().get(0).getField()).isEqualTo("amount");
            assertThat(plan.getAggregate().getGroupByFields()).containsExactly("transType");
            assertThat(plan.getAggregate().getOrderBy().get(0).getField()).isEqualTo("totalAmount");
            assertThat(plan.getAggregate().getMaxRows()).isEqualTo(20);
        }
    }

    @Nested
    @DisplayName("CLARIFY Plan 反序列化")
    class ClarifyPlanTest {

        @Test
        @DisplayName("从 golden fixture 正确解析 CLARIFY Plan")
        void shouldParseClarifyPlanFromFixture() throws Exception {
            PlanGenerateResponse response = readFixture("contracts/clarify-plan-v1.json");

            assertThat(response.getRequestId()).isEqualTo("turn-001");
            AgentPlan plan = response.getPlan();
            assertThat(plan.getIntent()).isEqualTo(AgentIntent.CLARIFY);
            assertThat(plan.getQuery()).isNull();
            assertThat(plan.getClarify()).isNotNull();
            assertThat(plan.getClarify().getQuestion()).isEqualTo("请提供姓名、工号或岗位等查询条件。");
        }
    }

    @Nested
    @DisplayName("未知字段/枚举拒绝")
    class UnknownFieldRejectionTest {

        @Test
        @DisplayName("未知 intent 值反序列化失败")
        void shouldRejectUnknownIntent() {
            String json = "{\"requestId\":\"1\",\"plan\":{\"planVersion\":\"1.0\",\"intent\":\"UPDATE\",\"domain\":\"employee\"}}";
            assertThatThrownBy(() -> MAPPER.readValue(json, PlanGenerateResponse.class))
                    .isNotNull();
        }

        @Test
        @DisplayName("未知 operator 值反序列化失败")
        void shouldRejectUnknownOperator() {
            String json = """
                {"requestId":"1","plan":{"planVersion":"1.0","intent":"QUERY","domain":"employee",\
                "query":{"filters":[{"field":"chineseName","operator":"REGEX","value":"test"}],"size":20}}}
                """;
            assertThatThrownBy(() -> MAPPER.readValue(json, PlanGenerateResponse.class))
                    .isNotNull();
        }

        @Test
        @DisplayName("未知 JSON 字段反序列化失败")
        void shouldRejectUnknownJsonField() {
            String json = """
                {"requestId":"1","plan":{"planVersion":"1.0","intent":"QUERY","domain":"employee",\
                "query":{"filters":[],"size":20},"extraField":"unexpected"}}
                """;
            assertThatThrownBy(() -> MAPPER.readValue(json, PlanGenerateResponse.class))
                    .isNotNull();
        }
    }

    @Nested
    @DisplayName("AgentChatRequest Bean Validation")
    class ChatRequestValidationTest {

        @Test
        @DisplayName("正常请求可创建")
        void shouldCreateValidRequest() {
            AgentChatRequest request = new AgentChatRequest();
            request.setMessage("查询岗位是HRM的员工");
            assertThat(request.getMessage()).isNotNull();
        }

        @Test
        @DisplayName("conversationId 为空时可为 null")
        void shouldAllowNullConversationId() {
            AgentChatRequest request = new AgentChatRequest();
            request.setMessage("test");
            assertThat(request.getConversationId()).isNull();
        }
    }

    @Nested
    @DisplayName("枚举值检查")
    class EnumValueTest {

        @Test
        @DisplayName("AgentIntent 包含 QUERY、CLARIFY 和 AGGREGATE")
        void shouldHaveQueryClarifyAndAggregate() {
            assertThat(AgentIntent.values()).containsExactly(
                    AgentIntent.QUERY, AgentIntent.CLARIFY, AgentIntent.AGGREGATE);
        }

        @Test
        @DisplayName("AgentOperator 包含八个规范值")
        void shouldHaveEightStandardOperators() {
            assertThat(AgentOperator.values())
                    .containsExactly(AgentOperator.EQ, AgentOperator.CONTAINS,
                            AgentOperator.CONTAINS_ANY, AgentOperator.STARTS_WITH,
                            AgentOperator.STARTS_WITH_ANY, AgentOperator.IN,
                            AgentOperator.GT, AgentOperator.LT);
        }

        @Test
        @DisplayName("AgentResponseType 收敛为三个值")
        void shouldHaveThreeResponseTypes() {
            assertThat(AgentResponseType.values())
                    .containsExactly(AgentResponseType.RESULT, AgentResponseType.CLARIFY,
                            AgentResponseType.ERROR);
        }

        @Test
        @DisplayName("RuntimeRole 只有 USER 和 ASSISTANT")
        void shouldHaveUserAndAssistant() {
            assertThat(RuntimeRole.values()).containsExactly(RuntimeRole.USER, RuntimeRole.ASSISTANT);
        }
    }

    @Nested
    @DisplayName("PlanGenerateRequest 序列化")
    class PlanGenerateRequestTest {

        @Test
        @DisplayName("domainSchemas 正确包含，不出现 domainSchema；capabilities 为必填字段")
        void shouldSerializeDomainSchemasWithoutOldField() throws Exception {
            PlanGenerateRequest req = new PlanGenerateRequest();
            req.setRequestId("req-1");
            req.setMessage("test");
            req.setDomainSchemas(java.util.List.of());
            req.setCapabilities(java.util.List.of());

            String json = MAPPER.writeValueAsString(req);

            assertThat(json).contains("domainSchemas");
            assertThat(json).doesNotContain("\"domainSchema\"");
            assertThat(json).contains("capabilities");
        }
    }

    private PlanGenerateResponse readFixture(String path) throws IOException {
        try (InputStream in = Thread.currentThread().getContextClassLoader().getResourceAsStream(path)) {
            if (in == null) {
                throw new AssertionError("Fixture not found: " + path);
            }
            return MAPPER.readValue(in, PlanGenerateResponse.class);
        }
    }
}
