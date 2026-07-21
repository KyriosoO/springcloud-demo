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
            if ("COMPATIBILITY".equals(fixture.path("stage").asText())) {
                ContractMetadata actual = (ContractMetadata) parser.parse(body, schema, type);
                ContractMetadata expected = new ContractMetadata()
                        .contractVersion(actual.getContractVersion())
                        .contractFingerprint(fixture.path("expectedContractFingerprint").asText())
                        .capabilities(new java.util.LinkedHashSet<>(actual.getCapabilities()));
                RuntimeCompatibilityDecision decision = new RuntimeCompatibilityGate().evaluate(
                        expected, actual, fixture.path("requiredCapability").asText(null));
                assertThat(decision.reason().name()).isEqualTo(fixture.path("expectedReason").asText());
                assertThat(errorCode(decision.reason())).isEqualTo(fixture.path("expectedCode").asText());
            } else if ("ACCEPT".equals(fixture.path("expectation").asText())) {
                assertThat(parser.parse(body, schema, type)).isInstanceOf(type);
            } else {
                assertThatThrownBy(() -> parser.parse(body, schema, type))
                        .isInstanceOf(ContractPayloadValidationException.class)
                        .hasMessage(ContractPayloadValidationException.CODE)
                        .hasNoCause()
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
        assertThatThrownBy(() -> parser.parse(
                "{\"capabilities\":[],\"contractFingerprint\":\"sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",\"contractVersion\":\"1.0.0\"}",
                "ContractMetadata", RuntimeError.class))
                .isInstanceOf(ContractPayloadValidationException.class);
    }

    private static String errorCode(RuntimeCompatibilityReason reason) {
        return reason == RuntimeCompatibilityReason.CAPABILITY_MISSING
                ? "RUNTIME_CAPABILITY_UNAVAILABLE"
                : "RUNTIME_CONTRACT_INCOMPATIBLE";
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
