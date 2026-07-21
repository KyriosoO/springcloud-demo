package com.dylan.baseline.agent.runtime;

import com.dylan.baseline.agent.api.runtime.generated.ContractMetadata;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.io.InputStream;
import java.util.LinkedHashSet;

public final class ContractLockMetadataLoader {
    static final String LOCK_RESOURCE = "openapi/agent-runtime-contract.lock.json";
    private final ObjectMapper objectMapper;

    public ContractLockMetadataLoader(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public ContractMetadata load() {
        try (InputStream stream = Thread.currentThread().getContextClassLoader().getResourceAsStream(LOCK_RESOURCE)) {
            if (stream == null) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            JsonNode lock = objectMapper.readTree(stream);
            if (lock.path("lockFormatVersion").asInt(-1) != 1) {
                throw new IllegalStateException("CONTRACT_LOCK_INVALID");
            }
            LinkedHashSet<String> capabilities = new LinkedHashSet<>();
            lock.path("capabilities").forEach(value -> capabilities.add(value.asText()));
            return new ContractMetadata()
                    .contractVersion(requiredText(lock, "contractVersion"))
                    .contractFingerprint(requiredText(lock, "contractFingerprint"))
                    .capabilities(capabilities);
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
