package com.dylan.baseline.agent.runtime;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.Schema;
import com.networknt.schema.SchemaRegistry;
import com.networknt.schema.SchemaRegistryConfig;
import com.networknt.schema.SpecificationVersion;
import java.io.InputStream;
import org.junit.jupiter.api.Test;

class ContractConformanceTest {
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void isolatedSchemaRejectsUnknownDiscriminatorAndWireSemanticDrift() throws Exception {
        Schema schema;
        try (InputStream stream = getClass().getClassLoader()
                .getResourceAsStream("contract/conformance/m1-conformance-schema.json")) {
            if (stream == null) throw new IllegalStateException("conformance schema missing");
            schema = SchemaRegistry.withDefaultDialect(
                            SpecificationVersion.DRAFT_2020_12,
                            builder -> builder.schemaRegistryConfig(SchemaRegistryConfig.builder()
                                    .formatAssertionsEnabled(true)
                                    .build()))
                    .getSchema(mapper.readTree(stream));
        }
        assertThat(schema.validate(json("""
                {"durationMs":0,"kind":"TYPE_A","occurredAt":"2026-07-21T00:00:00Z","valueA":"ok"}
                """))).isEmpty();
        for (String payload : new String[] {
                "{\"durationMs\":0,\"kind\":\"UNKNOWN\",\"occurredAt\":\"2026-07-21T00:00:00Z\"}",
                "{\"durationMs\":-1,\"kind\":\"TYPE_A\",\"occurredAt\":\"2026-07-21T00:00:00Z\",\"valueA\":\"x\"}",
                "{\"durationMs\":1.5,\"kind\":\"TYPE_A\",\"occurredAt\":\"2026-07-21T00:00:00Z\",\"valueA\":\"x\"}",
                "{\"durationMs\":1,\"kind\":\"TYPE_A\",\"occurredAt\":\"2026-07-21T00:00:00+08:00\",\"valueA\":\"x\"}",
                "{\"durationMs\":1,\"kind\":\"TYPE_A\",\"occurredAt\":\"2026-13-40T00:00:00Z\",\"valueA\":\"x\"}"
        }) {
            assertThat(schema.validate(json(payload))).isNotEmpty();
        }
    }

    private JsonNode json(String value) throws Exception {
        return mapper.readTree(value);
    }
}
