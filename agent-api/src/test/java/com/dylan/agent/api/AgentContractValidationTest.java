package com.dylan.agent.api;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import io.swagger.v3.core.util.Json;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.media.Schema;

/**
 * Agent 契约验证测试。
 * 验证 valid/invalid fixtures 对 Jackson 反序列化和 OpenAPI schema 的校验一致性。
 * 验证 OpenAPI artifact 自身的结构完整性。
 */
@DisplayName("AgentContractValidation")
class AgentContractValidationTest {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);
    private static OpenAPI OPEN_API;

    @BeforeAll
    static void loadOpenApiSpec() throws Exception {
        try (InputStream in = Thread.currentThread().getContextClassLoader()
                .getResourceAsStream("openapi/agent-runtime-openapi.json")) {
            assertThat(in).isNotNull();
            OPEN_API = Json.mapper().readValue(in, OpenAPI.class);
        }
    }

    private PlanGenerateResponse readFixture(String path) throws IOException {
        try (InputStream in = Thread.currentThread().getContextClassLoader()
                .getResourceAsStream(path)) {
            assertThat(in).as("Fixture not found: " + path).isNotNull();
            return MAPPER.readValue(in, PlanGenerateResponse.class);
        }
    }

    private JsonNode readFixtureAsNode(String path) throws IOException {
        try (InputStream in = Thread.currentThread().getContextClassLoader()
                .getResourceAsStream(path)) {
            assertThat(in).isNotNull();
            return MAPPER.readTree(in);
        }
    }

    @SuppressWarnings("unchecked")
    private boolean isValidAgainstSchema(JsonNode node, String schemaName) {
        Schema<Object> schema = (Schema<Object>) OPEN_API.getComponents().getSchemas().get(schemaName);
        if (schema == null) return true;
        if (schema.getEnum() != null && !schema.getEnum().isEmpty()) return true;
        Boolean addProp = (Boolean) schema.getAdditionalProperties();
        if (addProp != null && !addProp) {
            Set<String> allowed = schema.getProperties() != null
                    ? schema.getProperties().keySet() : Set.of();
            var fieldNames = node.fieldNames();
            while (fieldNames.hasNext()) {
                if (!allowed.contains(fieldNames.next())) return false;
            }
        }
        return true;
    }

    // ─── Valid fixtures ──────────────────────────────────────────

    @Nested
    @DisplayName("Valid fixture 反序列化 + 字段断言")
    class ValidFixtures {

        @Test
        @DisplayName("query-plan-v1.json")
        void queryPlanV1() throws Exception {
            PlanGenerateResponse resp = readFixture("contracts/query-plan-v1.json");
            assertThat(resp.getRequestId()).isEqualTo("turn-001");
            AgentPlan plan = resp.getPlan();
            assertThat(plan.getPlanVersion()).isEqualTo("1.0");
            assertThat(plan.getIntent().name()).isEqualTo("QUERY");
            assertThat(plan.getDomain()).isEqualTo("employee");
            assertThat(plan.getQuery()).isNotNull();
            assertThat(plan.getClarify()).isNull();
        }

        @Test
        @DisplayName("clarify-plan-v1.json")
        void clarifyPlanV1() throws Exception {
            PlanGenerateResponse resp = readFixture("contracts/clarify-plan-v1.json");
            AgentPlan plan = resp.getPlan();
            assertThat(plan.getIntent().name()).isEqualTo("CLARIFY");
            assertThat(plan.getClarify()).isNotNull();
            assertThat(plan.getQuery()).isNull();
        }

        @Test
        @DisplayName("aggregate-plan-v1.json")
        void aggregatePlanV1() throws Exception {
            PlanGenerateResponse resp = readFixture("contracts/aggregate-plan-v1.json");
            AgentPlan plan = resp.getPlan();
            assertThat(plan.getIntent().name()).isEqualTo("AGGREGATE");
            assertThat(plan.getDomain()).isEqualTo("transaction");
            assertThat(plan.getAggregate()).isNotNull();
            assertThat(plan.getQuery()).isNull();
            assertThat(plan.getClarify()).isNull();
            assertThat(plan.getAggregate().getMetrics()).hasSize(2);
            assertThat(plan.getAggregate().getMetrics().get(0).getFunction().name())
                    .isEqualTo("SUM");
            assertThat(plan.getAggregate().getMetrics().get(0).getField())
                    .isEqualTo("amount");
            assertThat(plan.getAggregate().getMetrics().get(1).getFunction().name())
                    .isEqualTo("COUNT");
            assertThat(plan.getAggregate().getMetrics().get(1).getField()).isNull();
            assertThat(plan.getAggregate().getGroupByFields()).containsExactly("transType");
            assertThat(plan.getAggregate().getMaxRows()).isEqualTo(20);
        }

        @Test
        @DisplayName("aggregate-plan 使用 maxRows 而非 bucketSize")
        void aggregatePlanUsesMaxRows() throws Exception {
            JsonNode node = readFixtureAsNode("contracts/aggregate-plan-v1.json");
            JsonNode plan = node.get("plan").get("aggregate");
            assertThat(plan.has("maxRows")).isTrue();
        }
    }

    // ─── 未知字段拒绝 ─────────────────────────────────────

    @Nested
    @DisplayName("Unknown field 拒绝（additionalProperties: false）")
    class UnknownFieldRejection {

        @Test
        @DisplayName("未知顶层 intent 值拒绝")
        void unknownIntentRejected() {
            assertThrows(Exception.class, () ->
                    MAPPER.readValue("""
                            {"planVersion":"1.0","intent":"UPDATE","domain":"employee"}""",
                            AgentPlan.class));
        }

        @Test
        @DisplayName("未知 JSON 属性拒绝")
        void unknownJsonFieldRejected() {
            assertThrows(Exception.class, () ->
                    MAPPER.readValue("""
                            {"requestId":"1","plan":{"planVersion":"1.0","intent":"QUERY",
                            "domain":"employee","query":{"filters":[],"size":20},
                            "extraField":"unexpected"}}""",
                            PlanGenerateResponse.class));
        }
    }

    // ─── OpenAPI artifact 自校验 ────────────────────────────────

    @Nested
    @DisplayName("OpenAPI artifact 自身结构")
    class OpenApiArtifactSelfCheck {

        @Test
        @DisplayName("是合法 OpenAPI 3.0")
        void validOpenApiVersion() {
            assertThat(OPEN_API.getOpenapi()).isEqualTo("3.0.1");
            assertThat(OPEN_API.getInfo().getTitle()).isNotEmpty();
            assertThat(OPEN_API.getComponents().getSchemas()).isNotEmpty();
        }

        @Test
        @DisplayName("包含所有 L1 结构契约 schema")
        void containsAllL1Schemas() {
            Map<String, Schema> schemas = OPEN_API.getComponents().getSchemas();
            List<String> required = List.of(
                    "AgentPlan", "AgentQuerySpec", "AgentFilter", "ClarifySpec",
                    "AgentAggregateSpec", "AggregateMetricSpec", "AggregateOrderSpec",
                    "PlanGenerateRequest", "PlanGenerateResponse", "RuntimeErrorResponse",
                    "RuntimeDomainSchema", "RuntimeFieldSchema", "RuntimeTurn",
                    "RuntimeQueryContext",
                    "AgentIntent", "AgentOperator", "AgentFieldType", "AggregateFunction"
            );
            required.forEach(name ->
                    assertThat(schemas).as("Missing schema: " + name).containsKey(name));
        }

        @Test
        @DisplayName("object schema 均设 additionalProperties: false")
        void objectSchemasDisallowAdditionalProps() {
            OPEN_API.getComponents().getSchemas().forEach((name, schema) -> {
                if (schema.getEnum() != null && !schema.getEnum().isEmpty()) return;
                if ("object".equals(schema.getType()) || schema.getProperties() != null) {
                    assertThat(schema.getAdditionalProperties())
                            .as("Schema %s missing additionalProperties: false", name)
                            .isEqualTo(false);
                }
            });
        }
    }
}
