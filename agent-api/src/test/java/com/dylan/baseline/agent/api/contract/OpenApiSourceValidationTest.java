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
        assertThat(source.toString()).doesNotContain("http://", "https://");
        assertThat(lock.path("lockFormatVersion").asInt()).isEqualTo(1);
        assertThat(lock.path("contractVersion").asText()).isEqualTo(source.path("info").path("version").asText());
        assertThat(lock.path("sourceSha256").asText()).isEqualTo(
                HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(sourceBytes)));
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
