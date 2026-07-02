package com.dylan.agent.api.contract;

import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

@DisplayName("Active Runtime OpenAPI")
@SuppressWarnings({"rawtypes", "unchecked", "deprecation"})
class AgentRuntimeContractOpenApiGenerationTest {

    private static final OpenAPI OPEN_API = AgentRuntimeContractOpenApiFactory.build();

    @Test
    void shouldBuildOpenApi31WithExactlyTwoPaths() {
        assertEquals("3.1.0", OPEN_API.getOpenapi());
        assertEquals(Set.of(
            AgentRuntimeContractOpenApiFactory.ROUTE_PATH,
            AgentRuntimeContractOpenApiFactory.PLAN_PATH), OPEN_API.getPaths().keySet());
        OPEN_API.getPaths().values().forEach(path -> assertNotNull(path.getPost()));
    }

    @Test
    void shouldUseSingleContractGenerationVersion() {
        assertEquals(AgentRuntimeContract.VERSION, OPEN_API.getInfo().getVersion());
        for (String requestName : List.of("RouteRequest", "PlanRequest")) {
            Schema request = OPEN_API.getComponents().getSchemas().get(requestName);
            assertTrue(request.getRequired().contains("contractVersion"));
            Schema version = (Schema) request.getProperties().get("contractVersion");
            assertEquals(List.of(AgentRuntimeContract.VERSION), version.getEnum());
        }
    }

    @Test
    void shouldExposeClosedDiscriminatedUnions() {
        assertDiscriminator("RouteOutcome", "outcomeType", Set.of("DECISION", "CLARIFICATION"));
        assertDiscriminator("PlanOutcome", "outcomeType", Set.of("EXECUTABLE", "CLARIFICATION"));
        assertDiscriminator("AgentPlan", "planKind", Set.of("QUERY", "AGGREGATE"));
        assertDiscriminator("ClarificationArgs", "argType", Set.of(
            "CAPABILITY_CHOICES", "DOMAIN_CHOICES", "FIELD_CHOICES", "VALUE_CHOICES"));
        assertDiscriminator("RuntimeContextView", "contextType", Set.of("QUERY", "AGGREGATE"));
    }

    @Test
    void shouldRejectAdditionalProperties() {
        objectSchemas(OPEN_API).forEach((name, schema) ->
            assertEquals(Boolean.FALSE, schema.getAdditionalProperties(),
                name + " must reject additional properties"));
    }

    @Test
    void shouldMarkRequiredFieldsNonNullable() {
        Map<String, Set<String>> required = new LinkedHashMap<>();
        required.put("RouteRequest", Set.of("requestId", "contractVersion", "message", "history",
            "profileBehavior", "capabilities", "domains", "absoluteDeadline", "repairLimit"));
        required.put("PlanRequest", Set.of("requestId", "contractVersion", "message", "history",
            "capabilityId", "planKind", "capability", "inputSchemaRef", "contextViews",
            "absoluteDeadline", "repairLimit"));
        required.put("RuntimeOperationMetadata", Set.of("operation", "providerAttempts",
            "repairAttempts", "repairDurationMs", "totalDurationMs", "terminationReason",
            "deadlineReached", "repairLimitReached"));
        required.put("RuntimeErrorResponse", Set.of("code", "message", "metadata", "diagnosticId"));
        required.put("ClarificationRequired", Set.of(
            "outcomeType", "requestId", "reasonCode", "args", "metadata"));
        required.put("RouteDecision", Set.of(
            "outcomeType", "requestId", "capabilityId", "metadata"));
        required.put("ExecutablePlan", Set.of("outcomeType", "requestId", "plan", "metadata"));
        required.forEach((name, fields) -> {
            Schema schema = OPEN_API.getComponents().getSchemas().get(name);
            assertNotNull(schema, name);
            assertTrue(new LinkedHashSet<>(schema.getRequired()).containsAll(fields), name);
            fields.forEach(field -> {
                Schema property = (Schema) schema.getProperties().get(field);
                assertNotNull(property, name + "." + field);
                assertFalse(Boolean.TRUE.equals(property.getNullable()), name + "." + field);
            });
        });
    }

    @Test
    void shouldResolveEveryReference() {
        AgentRuntimeContractOpenApiFactory.validateNoDanglingRefs(OPEN_API);
    }

    @Test
    void shouldExcludeLegacyContracts() {
        Set<String> schemas = OPEN_API.getComponents().getSchemas().keySet();
        for (String forbidden : List.of(
            "AgentIntent", "PlanGenerateRequest", "PlanGenerateResponse",
            "ClarifyAgentPlan", "PlanVersion", "ClarifySpec")) {
            assertFalse(schemas.contains(forbidden), forbidden);
        }
    }

    @Test
    void shouldRequireInternalServiceAuthentication() {
        assertTrue(OPEN_API.getSecurity() == null || OPEN_API.getSecurity().isEmpty());
        Map<String, SecurityScheme> schemes = OPEN_API.getComponents().getSecuritySchemes();
        assertEquals(Set.of(AgentRuntimeContractOpenApiFactory.INTERNAL_AUTH), schemes.keySet());
        SecurityScheme scheme = schemes.get(AgentRuntimeContractOpenApiFactory.INTERNAL_AUTH);
        assertEquals(SecurityScheme.Type.APIKEY, scheme.getType());
        assertEquals(SecurityScheme.In.HEADER, scheme.getIn());
        assertEquals("X-Agent-Runtime-Key", scheme.getName());
        OPEN_API.getPaths().values().forEach(path -> {
            Operation operation = path.getPost();
            assertEquals(1, operation.getSecurity().size());
            assertEquals(Set.of(AgentRuntimeContractOpenApiFactory.INTERNAL_AUTH),
                operation.getSecurity().getFirst().keySet());
        });
    }

    @Test
    void shouldExposeTypedRuntimeErrorsForAllFailureStatuses() {
        OPEN_API.getPaths().forEach((path, item) -> {
            Map<String, io.swagger.v3.oas.models.responses.ApiResponse> responses =
                item.getPost().getResponses();
            assertEquals(Set.of("200", "400", "401", "422", "500", "503", "504"),
                responses.keySet());
            for (String status : List.of("400", "401", "422", "500", "503", "504")) {
                Schema schema = responses.get(status).getContent().get("application/json").getSchema();
                assertEquals("#/components/schemas/RuntimeErrorResponse", schema.get$ref());
            }
            Schema success = responses.get("200").getContent().get("application/json").getSchema();
            assertFalse("#/components/schemas/RuntimeErrorResponse".equals(success.get$ref()));
        });
    }

    @Test
    void shouldMatchCommittedActiveArtifact() throws Exception {
        String fresh = AgentRuntimeContractOpenApiFactory.canonicalJson(OPEN_API);
        if (isUpdateEnabled()) {
            updateArtifactAtomically(fresh);
            return;
        }
        assertEquals(readArtifact(), fresh,
            "active OpenAPI drifted; regenerate explicitly with -Dagent.contract.update=true");
    }

    @Test
    void shouldBeDeterministicAcrossTwoBuilds() throws Exception {
        assertEquals(AgentRuntimeContractOpenApiFactory.canonicalJson(OPEN_API),
            AgentRuntimeContractOpenApiFactory.canonicalJson(
                AgentRuntimeContractOpenApiFactory.build()));
    }

    private static boolean isUpdateEnabled() {
        return Boolean.getBoolean("agent.contract.update");
    }

    private static String readArtifact() throws IOException {
        assertTrue(Files.isRegularFile(AgentRuntimeContractOpenApiFactory.ARTIFACT));
        return Files.readString(AgentRuntimeContractOpenApiFactory.ARTIFACT, StandardCharsets.UTF_8);
    }

    private static void updateArtifactAtomically(String content) throws IOException {
        Files.createDirectories(AgentRuntimeContractOpenApiFactory.ARTIFACT.getParent());
        java.nio.file.Path temporary = Files.createTempFile(
            AgentRuntimeContractOpenApiFactory.ARTIFACT.getParent(), ".agent-runtime-openapi-", ".tmp");
        try {
            Files.writeString(temporary, content, StandardCharsets.UTF_8);
            Files.move(temporary, AgentRuntimeContractOpenApiFactory.ARTIFACT,
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
        } finally {
            Files.deleteIfExists(temporary);
        }
    }

    private static void assertDiscriminator(String schemaName, String property, Set<String> values) {
        Schema schema = OPEN_API.getComponents().getSchemas().get(schemaName);
        assertNotNull(schema, schemaName);
        assertNotNull(schema.getDiscriminator(), schemaName);
        assertEquals(property, schema.getDiscriminator().getPropertyName());
        assertEquals(values, schema.getDiscriminator().getMapping().keySet());
        assertNotNull(schema.getOneOf(), schemaName);
        assertEquals(values.size(), schema.getOneOf().size());
        Set<String> mappedRefs = new LinkedHashSet<>(schema.getDiscriminator().getMapping().values());
        Set<String> oneOfRefs = new LinkedHashSet<>();
        schema.getOneOf().forEach(item -> oneOfRefs.add(((Schema<?>) item).get$ref()));
        assertEquals(mappedRefs, oneOfRefs, schemaName);
        schema.getDiscriminator().getMapping().forEach((value, reference) -> {
            String subtype = reference.substring(reference.lastIndexOf('/') + 1);
            Schema subtypeSchema = OPEN_API.getComponents().getSchemas().get(subtype);
            assertTrue(subtypeSchema.getRequired().contains(property), subtype);
            Schema discriminator = (Schema) subtypeSchema.getProperties().get(property);
            assertEquals(List.of(value), discriminator.getEnum(), subtype);
        });
    }

    private static Map<String, Schema> objectSchemas(OpenAPI api) {
        Map<String, Schema> result = new LinkedHashMap<>();
        api.getComponents().getSchemas().forEach((name, schema) -> {
            if ("object".equals(schema.getType()) || schema.getProperties() != null) {
                result.put(name, schema);
            }
        });
        return result;
    }
}
