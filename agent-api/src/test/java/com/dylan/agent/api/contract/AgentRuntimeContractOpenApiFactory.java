package com.dylan.agent.api.contract;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationArgs;
import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextView;
import com.dylan.agent.api.contract.runtime.error.RuntimeErrorResponse;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.plan.PlanRequest;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import io.swagger.v3.core.converter.AnnotatedType;
import io.swagger.v3.core.converter.ModelConverters;
import io.swagger.v3.core.converter.ResolvedSchema;
import io.swagger.v3.core.util.Json;
import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.Operation;
import io.swagger.v3.oas.models.PathItem;
import io.swagger.v3.oas.models.Paths;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.media.ComposedSchema;
import io.swagger.v3.oas.models.media.Content;
import io.swagger.v3.oas.models.media.MediaType;
import io.swagger.v3.oas.models.media.ObjectSchema;
import io.swagger.v3.oas.models.media.Schema;
import io.swagger.v3.oas.models.media.StringSchema;
import io.swagger.v3.oas.models.parameters.RequestBody;
import io.swagger.v3.oas.models.responses.ApiResponse;
import io.swagger.v3.oas.models.responses.ApiResponses;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;

import java.nio.file.Path;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Builds the isolated D01 candidate OpenAPI document directly from Java contracts. */
@SuppressWarnings({"rawtypes", "unchecked", "deprecation"})
final class AgentRuntimeContractOpenApiFactory {

    static final String ROUTE_PATH = "/runtime/route";
    static final String PLAN_PATH = "/runtime/plan";
    static final String INTERNAL_AUTH = "InternalServiceAuth";
    static final Path ARTIFACT = Path.of(
        "src/test/resources/contract/candidate/openapi/agent-runtime-openapi.json");

    private AgentRuntimeContractOpenApiFactory() {
    }

    static OpenAPI build() {
        ModelConverters converters = new ModelConverters();
        OpenAPI api = new OpenAPI()
            .openapi("3.1.0")
            .info(new Info().title("Agent Runtime API").version(AgentRuntimeContract.VERSION))
            .components(buildComponents(converters))
            .paths(new Paths()
                .addPathItem(ROUTE_PATH, buildRoutePath())
                .addPathItem(PLAN_PATH, buildPlanPath()));
        validateNoDanglingRefs(api);
        return api;
    }

    static Components buildComponents(ModelConverters converters) {
        Components components = new Components()
            .addSecuritySchemes(INTERNAL_AUTH, buildInternalServiceSecurity());
        Map<String, Schema> schemas = new LinkedHashMap<>();
        for (Class<?> root : List.of(
            RouteRequest.class,
            RouteOutcome.class,
            PlanRequest.class,
            PlanOutcome.class,
            AgentPlan.class,
            ClarificationArgs.class,
            RuntimeContextView.class,
            RuntimeErrorResponse.class
        )) {
            ResolvedSchema resolved = converters.readAllAsResolvedSchema(new AnnotatedType(root));
            if (resolved.referencedSchemas != null) {
                resolved.referencedSchemas.forEach(schemas::putIfAbsent);
            }
        }
        components.setSchemas(schemas);

        List<String> unions = List.of(
            "RouteOutcome", "PlanOutcome", "AgentPlan", "ClarificationArgs", "RuntimeContextView");
        Map<String, Map<String, Schema>> inheritedProperties = new LinkedHashMap<>();
        Map<String, String> discriminatorProperty = new LinkedHashMap<>();
        Map<String, String> discriminatorValue = new LinkedHashMap<>();
        for (String unionName : unions) {
            Schema union = schemas.get(unionName);
            if (union == null || union.getDiscriminator() == null
                || union.getDiscriminator().getMapping() == null) {
                throw new IllegalStateException("missing closed union schema: " + unionName);
            }
            inheritedProperties.put(unionName,
                union.getProperties() == null ? Map.of() : new LinkedHashMap<>(union.getProperties()));
            union.getDiscriminator().getMapping().forEach((value, reference) -> {
                String subtype = reference.substring(reference.lastIndexOf('/') + 1);
                String previousProperty = discriminatorProperty.putIfAbsent(
                    subtype, union.getDiscriminator().getPropertyName());
                String previousValue = discriminatorValue.putIfAbsent(subtype, value);
                if ((previousProperty != null
                    && !previousProperty.equals(union.getDiscriminator().getPropertyName()))
                    || (previousValue != null && !previousValue.equals(value))) {
                    throw new IllegalStateException("conflicting discriminator mapping for " + subtype);
                }
            });
        }

        for (Map.Entry<String, String> entry : discriminatorValue.entrySet()) {
            String subtypeName = entry.getKey();
            Schema original = schemas.get(subtypeName);
            if (original == null) {
                throw new IllegalStateException("missing discriminator subtype schema: " + subtypeName);
            }
            ObjectSchema flattened = new ObjectSchema();
            flattened.setDescription(original.getDescription());
            flattened.setRequired(original.getRequired() == null
                ? null : new ArrayList<>(new LinkedHashSet<>(original.getRequired())));
            Map<String, Schema> properties = new LinkedHashMap<>();
            if (original.getProperties() != null) {
                properties.putAll(original.getProperties());
            }
            if (original instanceof ComposedSchema composed && composed.getAllOf() != null) {
                for (Schema part : composed.getAllOf()) {
                    if (part.get$ref() != null) {
                        String base = part.get$ref().substring(part.get$ref().lastIndexOf('/') + 1);
                        properties.putAll(inheritedProperties.getOrDefault(base, Map.of()));
                    }
                    if (part.getProperties() != null) {
                        properties.putAll(part.getProperties());
                    }
                }
            }
            String propertyName = discriminatorProperty.get(subtypeName);
            Schema discriminatorSchema = properties.get(propertyName);
            if (discriminatorSchema == null) {
                discriminatorSchema = new Schema<>().type("string");
                properties.put(propertyName, discriminatorSchema);
            }
            discriminatorSchema.setEnum(List.of(entry.getValue()));
            flattened.setProperties(properties);
            flattened.setAdditionalProperties(false);
            schemas.put(subtypeName, flattened);
        }

        for (String unionName : unions) {
            Schema original = schemas.get(unionName);
            ComposedSchema union = new ComposedSchema();
            union.setDescription(original.getDescription());
            union.setDiscriminator(original.getDiscriminator());
            List<Schema> oneOf = new ArrayList<>();
            original.getDiscriminator().getMapping().values().forEach(reference ->
                oneOf.add(new Schema<>().$ref(reference)));
            union.setOneOf(oneOf);
            schemas.put(unionName, union);
        }

        for (String requestName : List.of("RouteRequest", "PlanRequest")) {
            Schema request = schemas.get(requestName);
            Schema version = request == null || request.getProperties() == null
                ? null : (Schema) request.getProperties().get("contractVersion");
            if (version == null) {
                throw new IllegalStateException("missing contractVersion schema: " + requestName);
            }
            version.setEnum(List.of(AgentRuntimeContract.VERSION));
        }

        Map<String, Class<? extends Enum<?>>> enumTypes = new LinkedHashMap<>();
        enumTypes.put("AgentPlanKind", com.dylan.agent.api.contract.runtime.common.AgentPlanKind.class);
        enumTypes.put("AgentDomainMode", com.dylan.agent.api.contract.runtime.common.AgentDomainMode.class);
        enumTypes.put("RuntimeOperationType", com.dylan.agent.api.contract.runtime.common.RuntimeOperationType.class);
        enumTypes.put("RuntimeOutcomeType", com.dylan.agent.api.contract.runtime.common.RuntimeOutcomeType.class);
        enumTypes.put("RuntimeTerminationReason", com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason.class);
        enumTypes.put("RuntimeTurnRole", com.dylan.agent.api.contract.runtime.common.RuntimeTurnRole.class);
        enumTypes.put("RuntimeContextType", com.dylan.agent.api.contract.runtime.common.RuntimeContextType.class);
        enumTypes.put("ClarificationReasonCode", com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode.class);
        enumTypes.put("ClarificationArgType", com.dylan.agent.api.contract.runtime.clarification.ClarificationArgType.class);
        enumTypes.put("RuntimeErrorCode", com.dylan.agent.api.contract.runtime.error.RuntimeErrorCode.class);
        enumTypes.put("AgentFieldType", com.dylan.agent.api.enums.AgentFieldType.class);
        enumTypes.put("AgentOperator", com.dylan.agent.api.enums.AgentOperator.class);
        enumTypes.put("AggregateFunction", com.dylan.agent.api.enums.AggregateFunction.class);
        enumTypes.put("QueryContextMode", com.dylan.agent.api.enums.QueryContextMode.class);
        enumTypes.forEach((name, type) -> {
            StringSchema enumSchema = new StringSchema();
            enumSchema.setEnum(Arrays.stream(type.getEnumConstants()).map(Enum::name).toList());
            schemas.put(name, enumSchema);
        });
        Map<String, String> enumByProperty = Map.ofEntries(
            Map.entry("planKind", "AgentPlanKind"),
            Map.entry("domainMode", "AgentDomainMode"),
            Map.entry("operation", "RuntimeOperationType"),
            Map.entry("outcomeType", "RuntimeOutcomeType"),
            Map.entry("terminationReason", "RuntimeTerminationReason"),
            Map.entry("role", "RuntimeTurnRole"),
            Map.entry("contextType", "RuntimeContextType"),
            Map.entry("reasonCode", "ClarificationReasonCode"),
            Map.entry("argType", "ClarificationArgType"),
            Map.entry("code", "RuntimeErrorCode"),
            Map.entry("type", "AgentFieldType"),
            Map.entry("operator", "AgentOperator"),
            Map.entry("operators", "AgentOperator"),
            Map.entry("aggregateFunctions", "AggregateFunction"),
            Map.entry("function", "AggregateFunction"),
            Map.entry("contextMode", "QueryContextMode"));

        ArrayDeque<Schema> pending = new ArrayDeque<>(schemas.values());
        Set<Schema> visited = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap<>());
        while (!pending.isEmpty()) {
            Schema schema = pending.removeFirst();
            if (schema == null || !visited.add(schema)) {
                continue;
            }
            if (schema.getEnum() == null && ("object".equals(schema.getType())
                || schema.getProperties() != null)) {
                schema.setAdditionalProperties(false);
            }
            if (schema.getProperties() != null) {
                schema.getProperties().replaceAll((propertyName, property) -> {
                    String enumName = enumByProperty.get(propertyName);
                    if (enumName == null) {
                        return property;
                    }
                    Schema propertySchema = (Schema) property;
                    Schema enumCandidate = propertySchema.getItems() == null
                        ? propertySchema : propertySchema.getItems();
                    if (enumCandidate.getEnum() == null || enumCandidate.getEnum().size() <= 1) {
                        return property;
                    }
                    if (propertySchema.getItems() != null) {
                        propertySchema.setItems(ref(enumName));
                        return propertySchema;
                    }
                    return ref(enumName);
                });
                pending.addAll(schema.getProperties().values());
            }
            if (schema.getItems() != null) {
                pending.add(schema.getItems());
            }
            if (schema instanceof ComposedSchema composed) {
                if (composed.getAllOf() != null) pending.addAll(composed.getAllOf());
                if (composed.getOneOf() != null) pending.addAll(composed.getOneOf());
                if (composed.getAnyOf() != null) pending.addAll(composed.getAnyOf());
            }
        }
        return components;
    }

    static SecurityScheme buildInternalServiceSecurity() {
        return new SecurityScheme()
            .type(SecurityScheme.Type.APIKEY)
            .in(SecurityScheme.In.HEADER)
            .name("X-Agent-Runtime-Key");
    }

    static PathItem buildRoutePath() {
        return new PathItem().post(operation(
            "generateRoute", ref("RouteRequest"), ref("RouteOutcome")));
    }

    static PathItem buildPlanPath() {
        return new PathItem().post(operation(
            "generatePlan", ref("PlanRequest"), ref("PlanOutcome")));
    }

    static Operation operation(String id, Schema<?> request, Schema<?> success) {
        ApiResponses responses = new ApiResponses().addApiResponse("200", new ApiResponse()
            .description("Success")
            .content(new Content().addMediaType("application/json", new MediaType().schema(success))));
        Map<String, String> failures = Map.of(
            "400", "Invalid request",
            "401", "Authentication failed",
            "422", "Semantic or output validation failed",
            "500", "Internal error",
            "503", "Provider unavailable",
            "504", "Deadline exceeded");
        failures.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry ->
            responses.addApiResponse(entry.getKey(), new ApiResponse()
                .description(entry.getValue())
                .content(new Content().addMediaType("application/json",
                    new MediaType().schema(ref("RuntimeErrorResponse"))))));
        return new Operation()
            .operationId(id)
            .addSecurityItem(new SecurityRequirement().addList(INTERNAL_AUTH))
            .requestBody(new RequestBody().required(true)
                .content(new Content().addMediaType("application/json", new MediaType().schema(request))))
            .responses(responses);
    }

    static Schema<?> ref(String schemaName) {
        return new Schema<>().$ref("#/components/schemas/" + schemaName);
    }

    static String canonicalJson(OpenAPI api) throws JsonProcessingException {
        ObjectMapper mapper = Json.mapper().copy()
            .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
            .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
            .enable(SerializationFeature.INDENT_OUTPUT);
        return mapper.writeValueAsString(api).replace("\r\n", "\n").stripTrailing() + "\n";
    }

    static void validateNoDanglingRefs(OpenAPI api) {
        Set<String> schemas = api.getComponents() == null || api.getComponents().getSchemas() == null
            ? Set.of() : api.getComponents().getSchemas().keySet();
        JsonNode root = Json.mapper().valueToTree(api);
        ArrayDeque<JsonNode> pending = new ArrayDeque<>();
        pending.add(root);
        List<String> dangling = new ArrayList<>();
        while (!pending.isEmpty()) {
            JsonNode node = pending.removeFirst();
            if (node.isObject()) {
                node.fields().forEachRemaining(entry -> {
                    if ("$ref".equals(entry.getKey()) && entry.getValue().isTextual()) {
                        String reference = entry.getValue().asText();
                        String prefix = "#/components/schemas/";
                        if (!reference.startsWith(prefix)
                            || !schemas.contains(reference.substring(prefix.length()))) {
                            dangling.add(reference);
                        }
                    } else {
                        pending.add(entry.getValue());
                    }
                });
            } else if (node.isArray()) {
                node.forEach(pending::add);
            }
        }
        if (!dangling.isEmpty()) {
            throw new IllegalStateException("dangling OpenAPI refs: " + dangling);
        }
    }
}
