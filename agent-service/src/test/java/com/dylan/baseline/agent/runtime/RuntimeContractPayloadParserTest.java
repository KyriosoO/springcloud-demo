package com.dylan.baseline.agent.runtime;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;
import com.dylan.baseline.agent.api.runtime.generated.RuntimeError;
import com.dylan.baseline.agent.api.runtime.generated.RuntimeReadiness;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Validation;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.junit.jupiter.api.Test;

class RuntimeContractPayloadParserTest {
    private final ObjectMapper mapper = new ObjectMapper();
    private final RuntimeContractPayloadParser parser = new RuntimeContractPayloadParser(
            mapper, Validation.buildDefaultValidatorFactory().getValidator());

    @Test
    void appliesAllSharedFixtures() throws Exception {
        JsonNode manifest = readJson("contract/fixtures/agent-runtime/manifest.json");
        Map<String, Class<?>> types = Map.of(
                "ContractMetadata", ContractMetadata.class,
                "RuntimeError", RuntimeError.class,
                "RuntimeReadiness", RuntimeReadiness.class);
        for (JsonNode fixture : manifest.path("fixtures")) {
            String body = readText("contract/fixtures/agent-runtime/" + fixture.path("file").asText());
            String schema = fixture.path("schema").asText();
            Class<?> type = types.get(schema);
            if ("ACCEPT".equals(fixture.path("expectation").asText())) {
                assertThat(parser.parse(body, schema, type)).isInstanceOf(type);
            } else {
                assertThatThrownBy(() -> parser.parse(body, schema, type))
                        .isInstanceOf(ContractPayloadValidationException.class)
                        .hasMessage(ContractPayloadValidationException.CODE)
                        .doesNotHaveToString(body);
            }
        }
    }

    @Test
    void rejectsDuplicateKeysAndTrailingTokens() {
        assertThatThrownBy(() -> parser.parse("{\"capabilities\":[],\"capabilities\":[]}",
                "ContractMetadata", ContractMetadata.class))
                .isInstanceOf(ContractPayloadValidationException.class);
        assertThatThrownBy(() -> parser.parse("{} {}", "ContractMetadata", ContractMetadata.class))
                .isInstanceOf(ContractPayloadValidationException.class);
    }

    private JsonNode readJson(String resource) throws Exception {
        return mapper.readTree(readText(resource));
    }

    private String readText(String resource) throws Exception {
        try (InputStream stream = getClass().getClassLoader().getResourceAsStream(resource)) {
            if (stream == null) throw new IllegalStateException(resource);
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }
}
