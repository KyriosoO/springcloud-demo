package com.dylan.baseline.agent.runtime;

import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SchemaRegistryConfig;
import com.networknt.schema.SpecificationVersion;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validator;
import java.io.InputStream;
import java.util.Map;
import java.util.Set;

public final class RuntimeContractPayloadParser {
    private static final String OPENAPI_RESOURCE = "openapi/agent-runtime-openapi.json";
    private static final Map<String, Class<?>> ALLOWED_SCHEMAS = Map.of(
            "ContractMetadata", com.dylan.baseline.agent.api.runtime.generated.ContractMetadata.class,
            "RuntimeError", com.dylan.baseline.agent.api.runtime.generated.RuntimeError.class,
            "RuntimeReadiness", com.dylan.baseline.agent.api.runtime.generated.RuntimeReadiness.class);

    private final ObjectMapper objectMapper;
    private final Validator validator;
    private final Map<String, Schema> schemas;
    private final SchemaRegistry schemaRegistry = SchemaRegistry.withDefaultDialect(
            SpecificationVersion.DRAFT_2020_12,
            builder -> builder.schemaRegistryConfig(
                    SchemaRegistryConfig.builder().formatAssertionsEnabled(true).build()));

    public RuntimeContractPayloadParser(ObjectMapper baseMapper, Validator validator) {
        this.objectMapper = baseMapper.copy()
                .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION.mappedFeature())
                .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS)
                .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
        this.validator = validator;
        JsonNode definitions = loadDefinitions();
        this.schemas = ALLOWED_SCHEMAS.keySet().stream().collect(java.util.stream.Collectors.toUnmodifiableMap(
                name -> name, name -> schemaRegistry.getSchema(schemaDocument(definitions, name))));
    }

    public <T> T parse(String rawJson, String schemaName, Class<T> targetType) {
        if (ALLOWED_SCHEMAS.get(schemaName) != targetType) {
            throw new ContractPayloadValidationException();
        }
        try {
            JsonNode payload = objectMapper.readTree(rawJson);
            Schema schema = schemas.get(schemaName);
            if (!schema.validate(payload).isEmpty()) {
                throw new IllegalArgumentException("schema rejected payload");
            }
            T model = objectMapper.treeToValue(payload, targetType);
            Set<ConstraintViolation<T>> violations = validator.validate(model);
            if (!violations.isEmpty()) {
                throw new IllegalArgumentException("bean validation rejected payload");
            }
            return model;
        } catch (Exception exception) {
            throw new ContractPayloadValidationException();
        }
    }

    private JsonNode loadDefinitions() {
        try (InputStream stream = Thread.currentThread().getContextClassLoader()
                .getResourceAsStream(OPENAPI_RESOURCE)) {
            if (stream == null) {
                throw new IllegalStateException("CONTRACT_SCHEMA_INVALID");
            }
            JsonNode schemas = objectMapper.readTree(stream).path("components").path("schemas").deepCopy();
            rewriteReferences(schemas);
            return schemas;
        } catch (Exception exception) {
            throw new IllegalStateException("CONTRACT_SCHEMA_INVALID", exception);
        }
    }

    private JsonNode schemaDocument(JsonNode definitions, String schemaName) {
        var root = objectMapper.createObjectNode();
        root.put("$schema", "https://json-schema.org/draft/2020-12/schema");
        root.set("$defs", definitions);
        root.put("$ref", "#/$defs/" + schemaName);
        return root;
    }

    private static void rewriteReferences(JsonNode node) {
        if (node.isObject()) {
            JsonNode ref = node.get("$ref");
            if (ref != null) {
                String value = ref.asText();
                String prefix = "#/components/schemas/";
                if (!value.startsWith(prefix)) {
                    throw new IllegalStateException("CONTRACT_SCHEMA_INVALID");
                }
                ((com.fasterxml.jackson.databind.node.ObjectNode) node)
                        .put("$ref", "#/$defs/" + value.substring(prefix.length()));
            }
            node.properties().forEach(field -> rewriteReferences(field.getValue()));
        } else if (node.isArray()) {
            node.forEach(RuntimeContractPayloadParser::rewriteReferences);
        }
    }
}
