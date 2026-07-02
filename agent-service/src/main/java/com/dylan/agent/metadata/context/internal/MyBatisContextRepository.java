package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.InvocationScope;
import com.dylan.agent.invocation.model.RunScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Repository;

import java.io.IOException;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.Objects;
import java.util.Optional;

/**
 * 基于 MyBatis 的 ContextRepository。
 */
@Repository
public class MyBatisContextRepository implements ContextRepository {

    private final ContextRecordMapper mapper;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public MyBatisContextRepository(ContextRecordMapper mapper, ObjectMapper objectMapper, Clock clock) {
        this.mapper = Objects.requireNonNull(mapper);
        this.objectMapper = Objects.requireNonNull(objectMapper).copy();
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public Optional<ContextRecordEntity> findCurrent(ContextRecordKey key, Instant now) {
        ContextRecordRow row = mapper.findCurrent(
                key.owner().type(),
                key.owner().id(),
                scopeType(key.scope()),
                key.scope().scopeId(),
                key.contextType().name(),
                LocalDateTime.ofInstant(now, clock.getZone()));
        return Optional.ofNullable(row).map(this::toEntity);
    }

    @Override
    public void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion) {
        Objects.requireNonNull(record, "record must not be null");
        Objects.requireNonNull(expectedVersion, "expectedVersion must not be null");
        Optional<ContextRecordEntity> current = findCurrent(record.recordKey(), clock.instant());
        if (expectedVersion.expectsAbsent()) {
            if (current.isPresent()) {
                throw new IllegalStateException("context record already exists: " + record.recordKey().contextType());
            }
        } else {
            long expectedCurrent = expectedVersion.targetVersion() - 1;
            if (current.isEmpty() || current.orElseThrow().recordVersion() != expectedCurrent) {
                throw new IllegalStateException("context record version conflict: " + record.recordKey().contextType());
            }
        }
        if (record.recordVersion() != expectedVersion.targetVersion()) {
            throw new IllegalStateException("record version does not match expected target");
        }
        if (mapper.upsert(toRow(record)) != 1) {
            throw new IllegalStateException("upsert context record failed");
        }
    }

    @Override
    public void markConversationUnreadable(ConversationScope scope, Instant now) {
        mapper.markConversationUnreadable(
                scope.scopeId(),
                LocalDateTime.ofInstant(now, clock.getZone()));
    }

    @Override
    public int deleteExpired(Instant cutoff, int limit) {
        if (limit <= 0) {
            throw new IllegalArgumentException("limit must be positive");
        }
        return mapper.deleteExpired(LocalDateTime.ofInstant(cutoff, clock.getZone()), limit);
    }

    private ContextRecordEntity toEntity(ContextRecordRow row) {
        return new ContextRecordEntity(
                row.getContextId(),
                new ContextRecordKey(
                        new ContextOwnerRef(row.getOwnerType(), row.getOwnerId()),
                        scope(row.getScopeType(), row.getScopeId()),
                        RuntimeContextType.valueOf(row.getContextType())),
                new ContractRef(row.getContractSchema(), row.getContractVersion()),
                row.getRecordVersion(),
                protectedPayload(row.getProtectedPayloadJson()),
                row.getSourceCapabilityId(),
                row.getSourceInvocationId(),
                row.getSourceDomain(),
                row.getExpiresAt().atZone(clock.getZone()).toInstant());
    }

    private ContextRecordRow toRow(ContextRecordEntity entity) {
        ContextRecordRow row = new ContextRecordRow();
        row.setContextId(entity.contextId());
        row.setOwnerType(entity.recordKey().owner().type());
        row.setOwnerId(entity.recordKey().owner().id());
        row.setScopeType(scopeType(entity.recordKey().scope()));
        row.setScopeId(entity.recordKey().scope().scopeId());
        row.setContextType(entity.recordKey().contextType().name());
        row.setContractSchema(entity.contractRef().schema());
        row.setContractVersion(entity.contractRef().version());
        row.setRecordVersion(entity.recordVersion());
        row.setProtectedPayloadJson(writeProtectedPayload(entity.protectedPayload()));
        row.setSourceCapabilityId(entity.sourceCapabilityId());
        row.setSourceInvocationId(entity.sourceInvocationId());
        row.setSourceDomain(entity.sourceDomain());
        row.setReadable(true);
        row.setExpiresAt(LocalDateTime.ofInstant(entity.expiresAt(), clock.getZone()));
        row.setUpdatedAt(LocalDateTime.now(clock));
        return row;
    }

    private static String scopeType(InvocationScope scope) {
        if (scope instanceof ConversationScope) {
            return "CONVERSATION";
        }
        if (scope instanceof RunScope) {
            return "RUN";
        }
        throw new IllegalArgumentException("unsupported scope: " + scope.getClass().getName());
    }

    private static InvocationScope scope(String scopeType, String scopeId) {
        return switch (scopeType) {
            case "CONVERSATION" -> new ConversationScope(scopeId);
            case "RUN" -> new RunScope(scopeId);
            default -> throw new IllegalArgumentException("unsupported scopeType: " + scopeType);
        };
    }

    private String writeProtectedPayload(ProtectedPayload payload) {
        try {
            return objectMapper.writeValueAsString(new ProtectedPayloadJson(
                    Base64.getEncoder().encodeToString(payload.ciphertext()),
                    payload.keyId(),
                    Base64.getEncoder().encodeToString(payload.nonce()),
                    payload.algorithmVersion()));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("serialize protected payload failed", ex);
        }
    }

    private ProtectedPayload protectedPayload(String json) {
        try {
            ProtectedPayloadJson payload = objectMapper.readValue(json, ProtectedPayloadJson.class);
            return new ProtectedPayload(
                    Base64.getDecoder().decode(payload.ciphertext()),
                    payload.keyId(),
                    Base64.getDecoder().decode(payload.nonce()),
                    payload.algorithmVersion());
        } catch (IOException ex) {
            throw new IllegalStateException("deserialize protected payload failed", ex);
        }
    }

    private record ProtectedPayloadJson(
            String ciphertext,
            String keyId,
            String nonce,
            String algorithmVersion) {
    }
}
