package com.dylan.baseline.agent.runtime;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;
import com.fasterxml.jackson.core.StreamReadFeature;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.regex.Pattern;

public final class ContractLockMetadataLoader {
    static final String LOCK_RESOURCE = "openapi/agent-runtime-contract.lock.json";
    private static final String SOURCE_PATH = "agent-api/src/main/resources/openapi/agent-runtime-openapi.json";
    private static final Pattern VERSION = Pattern.compile(
            "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?(?:\\+[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?$");
    private static final Pattern SHA256 = Pattern.compile("^[a-f0-9]{64}$");
    private final ObjectMapper objectMapper;

    public ContractLockMetadataLoader(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper.copy()
                .enable(StreamReadFeature.STRICT_DUPLICATE_DETECTION.mappedFeature())
                .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
    }

    public ContractMetadata load() {
        try (InputStream stream = Thread.currentThread().getContextClassLoader().getResourceAsStream(LOCK_RESOURCE)) {
            if (stream == null) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            return load(stream);
        } catch (IOException | RuntimeException exception) {
            throw new IllegalStateException("CONTRACT_LOCK_INVALID", exception);
        }
    }

    ContractMetadata load(InputStream stream) {
        try {
            JsonNode lock = objectMapper.readTree(stream);
            if (!lock.isObject() || lock.path("lockFormatVersion").asInt(-1) != 1
                    || !SOURCE_PATH.equals(lock.path("sourcePath").asText())) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            String version = requiredText(lock, "contractVersion");
            String fingerprint = requiredText(lock, "contractFingerprint");
            String sourceSha256 = requiredText(lock, "sourceSha256");
            if (!VERSION.matcher(version).matches() || !SHA256.matcher(sourceSha256).matches()
                    || !fingerprint.equals("sha256:" + sourceSha256)) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            JsonNode capabilityNode = lock.path("capabilities");
            if (!capabilityNode.isArray()) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            List<String> orderedCapabilities = new ArrayList<>();
            capabilityNode.forEach(value -> {
                if (!value.isTextual() || value.asText().isBlank()) {
                    throw new IllegalStateException("CONTRACT_LOCK_INVALID");
                }
                orderedCapabilities.add(value.asText());
            });
            List<String> sortedUnique = orderedCapabilities.stream().distinct().sorted().toList();
            if (!orderedCapabilities.equals(sortedUnique)) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            return new ContractMetadata()
                    .contractVersion(version)
                    .contractFingerprint(fingerprint)
                    .capabilities(new LinkedHashSet<>(orderedCapabilities));
        } catch (IOException | RuntimeException exception) {
            throw new IllegalStateException("CONTRACT_LOCK_INVALID", exception);
        }
    }

    private static String requiredText(JsonNode node, String field) {
        String value = node.path(field).asText("");
        if (value.isBlank()) {
            throw new IllegalStateException("CONTRACT_LOCK_INVALID");
        }
        return value;
    }
}
