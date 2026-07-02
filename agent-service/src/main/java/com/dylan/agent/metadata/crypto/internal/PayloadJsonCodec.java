package com.dylan.agent.metadata.crypto.internal;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.response.AgentResultPayload;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.io.IOException;
import java.util.Objects;

/**
 * encrypted context/result payload 使用的严格 JSON codec。
 */
public final class PayloadJsonCodec {

    private final ObjectMapper mapper;

    public PayloadJsonCodec() {
        this(JsonMapper.builder()
                .addModule(new JavaTimeModule())
                .disable(MapperFeature.DEFAULT_VIEW_INCLUSION)
                .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
                .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
                .build()
                .findAndRegisterModules());
    }

    @SuppressWarnings("deprecation")
    public PayloadJsonCodec(ObjectMapper mapper) {
        this.mapper = Objects.requireNonNull(mapper).copy()
                .registerModule(new JavaTimeModule());
        this.mapper.deactivateDefaultTyping();
        this.mapper.configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true);
        this.mapper.configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_INVALID_SUBTYPE, true);
        this.mapper.configure(com.fasterxml.jackson.databind.DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES, true);
        this.mapper.configure(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY, true);
        this.mapper.configure(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS, true);
    }

    public byte[] serialize(Object value, Class<?> expectedType) {
        Objects.requireNonNull(value, "value must not be null");
        Objects.requireNonNull(expectedType, "expectedType must not be null");
        assertAllowedRoot(expectedType);
        if (!expectedType.isInstance(value)) {
            throw new IllegalArgumentException("value does not match expectedType");
        }
        try {
            return mapper.writerFor(expectedType).writeValueAsBytes(value);
        } catch (IOException ex) {
            throw new IllegalStateException("payload serialization failed", ex);
        }
    }

    public <T> T deserialize(byte[] bytes, Class<T> expectedType) {
        Objects.requireNonNull(bytes, "bytes must not be null");
        Objects.requireNonNull(expectedType, "expectedType must not be null");
        assertAllowedRoot(expectedType);
        try {
            return mapper.readerFor(expectedType).readValue(bytes);
        } catch (IOException ex) {
            throw new IllegalStateException("payload deserialization failed", ex);
        }
    }

    private static void assertAllowedRoot(Class<?> expectedType) {
        if (!CapabilityContextPayload.class.isAssignableFrom(expectedType)
                && !AgentResultPayload.class.isAssignableFrom(expectedType)) {
            throw new IllegalArgumentException(
                    "payload root must be CapabilityContextPayload or AgentResultPayload subtype");
        }
    }
}
