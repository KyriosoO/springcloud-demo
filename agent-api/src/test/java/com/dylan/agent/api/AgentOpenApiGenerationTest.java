package com.dylan.agent.api;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import com.dylan.agent.api.capability.AgentCapabilityDescriptor;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.capability.CapabilityContextSpec;
import com.dylan.agent.api.capability.CapabilityContractRef;
import com.dylan.agent.api.capability.CapabilityDomainScope;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.enums.QueryContextMode;
import com.dylan.agent.api.enums.RuntimeRole;
import com.dylan.agent.api.plan.AgentAggregateSpec;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.plan.AggregateOrderSpec;
import com.dylan.agent.api.plan.ClarifySpec;
import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.response.RuntimeErrorResponse;
import com.dylan.agent.api.runtime.RuntimeAggregateContext;
import com.dylan.agent.api.runtime.RuntimeDomainSchema;
import com.dylan.agent.api.runtime.RuntimeFieldSchema;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.api.runtime.RuntimeTurn;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.node.ObjectNode;

import io.swagger.v3.core.converter.AnnotatedType;
import io.swagger.v3.core.converter.ModelConverters;
import io.swagger.v3.core.converter.ResolvedSchema;
import io.swagger.v3.core.util.Json;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.Schema;

/**
 * OpenAPI 3.0 生成测试。
 * 从 agent-api annotated DTO 生成 OpenAPI spec，与已提交的 artifact 比较。
 * 设 agent.contract.update=true 可重写产物文件。
 */
class AgentOpenApiGenerationTest {

    private static final Path OUTPUT_PATH = Paths.get(
            "src/main/resources/openapi/agent-runtime-openapi.json");

    private static final boolean UPDATE_MODE = Boolean.parseBoolean(
            System.getProperty("agent.contract.update", "false"));

    /** L1 结构契约中所有需要生成 schema 的 DTO 类和枚举类。 */
    private static final Class<?>[] CONTRACT_CLASSES = {
            // enums
            AgentIntent.class, AgentOperator.class, AgentFieldType.class,
            AggregateFunction.class, AgentResponseType.class, AgentErrorCode.class,
            QueryContextMode.class, RuntimeRole.class,
            // plan DTOs
            AgentPlan.class, AgentQuerySpec.class, AgentFilter.class, ClarifySpec.class,
            AgentAggregateSpec.class, AggregateMetricSpec.class, AggregateOrderSpec.class,
            // request/response
            PlanGenerateRequest.class, PlanGenerateResponse.class, RuntimeErrorResponse.class,
            // capacity DTOs
            AgentCapabilityDescriptor.class, AgentCapabilityRiskLevel.class,
            AgentCapabilityExecutionMode.class, CapabilityDomainScope.class,
            CapabilityContractRef.class, CapabilityContextSpec.class,
            // runtime DTOs
            RuntimeDomainSchema.class, RuntimeFieldSchema.class,
            RuntimeTurn.class, RuntimeQueryContext.class,
            RuntimeAggregateContext.class,
    };

    private final ObjectMapper mapper = Json.mapper()
            .enable(SerializationFeature.INDENT_OUTPUT)
            .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS);

    @Test
    @DisplayName("生成的 OpenAPI spec 与已提交的 artifact 一致")
    void shouldGenerateOpenApiMatchingCommittedArtifact() throws Exception {
        OpenAPI generated = buildOpenApi();
        String generatedJson = mapper.writeValueAsString(generated);

        if (UPDATE_MODE) {
            Files.createDirectories(OUTPUT_PATH.getParent());
            Files.writeString(OUTPUT_PATH, generatedJson);
            return;
        }

        String committedJson;
        try (InputStream in = Thread.currentThread().getContextClassLoader()
                .getResourceAsStream("openapi/agent-runtime-openapi.json")) {
            assertNotNull(in, "OpenAPI artifact not found at openapi/agent-runtime-openapi.json. "
                    + "Run with -Dagent.contract.update=true to generate.");
            committedJson = new String(in.readAllBytes());
        }

        JsonNode generatedNode = mapper.readTree(generatedJson);
        JsonNode committedNode = mapper.readTree(committedJson);
        assertEquals(committedNode, generatedNode,
                "OpenAPI spec 与已提交的 artifact 不一致。"
                + " 运行 'mvn -pl ../agent-api -am -Dagent.contract.update=true test' 重新生成。");
    }

    private OpenAPI buildOpenApi() {
        OpenAPI openApi = new OpenAPI();
        openApi.openapi("3.0.1");
        openApi.info(new Info()
                .title("Agent Runtime API")
                .version("1.0")
                .description("Agent Runtime plan generation API contract. "
                        + "Auto-generated from agent-api DTO annotations. DO NOT EDIT."));

        io.swagger.v3.oas.models.Components components =
                new io.swagger.v3.oas.models.Components();

        for (Class<?> clazz : CONTRACT_CLASSES) {
            ResolvedSchema resolved = ModelConverters.getInstance()
                    .readAllAsResolvedSchema(new AnnotatedType(clazz));
            resolved.referencedSchemas.forEach((name, schema) -> {
                if (!components.getSchemas().containsKey(name)) {
                    components.addSchemas(name, enforceAdditionalPropertiesFalse(schema, name));
                }
            });
            if (resolved.schema != null) {
                String name = clazz.getSimpleName();
                Schema<?> cleaned = enforceAdditionalPropertiesFalse(resolved.schema, name);
                components.addSchemas(name, cleaned);
            }
        }

        openApi.setComponents(components);
        return openApi;
    }

    /** 对所有 object 类型的 schema 强制 additionalProperties: false；枚举（有 enum 值）则跳过。 */
    @SuppressWarnings({"rawtypes", "unchecked"})
    private Schema enforceAdditionalPropertiesFalse(Schema schema, String name) {
        if (schema.getEnum() != null && !schema.getEnum().isEmpty()) {
            return schema;
        }
        if ("object".equals(schema.getType()) || schema.getProperties() != null) {
            schema.setAdditionalProperties(false);
        }
        if (schema.getProperties() != null) {
            schema.getProperties().forEach((propName, propSchema) -> {
                if (propSchema instanceof Schema ps
                        && ps.get$ref() == null
                        && "object".equals(ps.getType())) {
                    ps.setAdditionalProperties(false);
                }
            });
        }
        return schema;
    }
}
