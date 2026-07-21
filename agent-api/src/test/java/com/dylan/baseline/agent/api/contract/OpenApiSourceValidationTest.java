package com.dylan.baseline.agent.api.contract;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.InputStream;
import java.security.MessageDigest;
import java.util.HexFormat;
import org.junit.jupiter.api.Test;

class OpenApiSourceValidationTest {
    private final ObjectMapper mapper = new ObjectMapper();

    @Test
    void sourceAndFixtureManifestMatchLock() throws Exception {
        byte[] sourceBytes = bytes("openapi/agent-runtime-openapi.json");
        JsonNode source = mapper.readTree(sourceBytes);
        JsonNode lock = read("openapi/agent-runtime-contract.lock.json");
        assertThat(source.path("openapi").asText()).startsWith("3.1.");
        assertNoRemoteOrDanglingRefs(source, source.path("components").path("schemas"));
        assertThat(lock.path("lockFormatVersion").asInt()).isEqualTo(1);
        assertThat(lock.path("sourcePath").asText())
                .isEqualTo("agent-api/src/main/resources/openapi/agent-runtime-openapi.json");
        assertThat(lock.path("javaGenerator").path("configSha256").asText()).hasSize(64);
        assertThat(lock.path("pythonGenerator").path("configSha256").asText()).hasSize(64);
        assertThat(lock.path("generatedArtifacts").isArray()).isTrue();
        assertThat(lock.path("contractVersion").asText()).isEqualTo(source.path("info").path("version").asText());
        assertThat(lock.path("sourceSha256").asText()).isEqualTo(
                HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(sourceBytes)));
    }

    private void assertNoRemoteOrDanglingRefs(JsonNode node, JsonNode schemas) {
        if (node.isObject()) {
            JsonNode ref = node.get("$ref");
            if (ref != null) {
                assertThat(ref.asText()).startsWith("#/components/schemas/");
                assertThat(schemas.has(ref.asText().substring("#/components/schemas/".length()))).isTrue();
            }
            node.properties().forEach(field -> assertNoRemoteOrDanglingRefs(field.getValue(), schemas));
        } else if (node.isArray()) {
            node.forEach(child -> assertNoRemoteOrDanglingRefs(child, schemas));
        }
    }

    @Test
    void fixtureHashesMatchManifest() throws Exception {
        JsonNode manifest = read("contract/fixtures/agent-runtime/manifest.json");
        for (JsonNode fixture : manifest.path("fixtures")) {
            byte[] content = bytes("contract/fixtures/agent-runtime/" + fixture.path("file").asText());
            assertThat(HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(content)))
                    .isEqualTo(fixture.path("sha256").asText());
        }
    }

    private JsonNode read(String resource) throws Exception {
        return mapper.readTree(bytes(resource));
    }

    private byte[] bytes(String resource) throws Exception {
        try (InputStream stream = getClass().getClassLoader().getResourceAsStream(resource)) {
            if (stream == null) throw new IllegalStateException(resource);
            return stream.readAllBytes();
        }
    }
}
