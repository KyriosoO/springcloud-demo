package com.dylan.agent.lifecycle;

import com.dylan.agent.lifecycle.model.PlanningCheckpoint;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.Objects;

/**
 * 仅用于生命周期审计值的 JSON 编解码器。
 */
@Component
public class InvocationAuditJsonCodec {

    private final ObjectMapper objectMapper;

    public InvocationAuditJsonCodec(ObjectMapper objectMapper) {
        this.objectMapper = Objects.requireNonNull(objectMapper).copy();
    }

    public String writeCheckpoint(PlanningCheckpoint checkpoint) {
        Objects.requireNonNull(checkpoint, "checkpoint must not be null");
        try {
            return objectMapper.writeValueAsString(checkpoint);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("serialize planning checkpoint failed", ex);
        }
    }
}
