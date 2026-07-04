package com.dylan.agent.metadata.context.internal;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.fasterxml.jackson.databind.ObjectMapper;

class MyBatisContextRepositoryTest {

    private static final Clock CLOCK =
            Clock.fixed(Instant.parse("2026-07-01T00:00:00Z"), ZoneOffset.UTC);

    @Test
    void upsertApprovedAcceptsDuplicateKeyUpdateAffectedRows() {
        ContextRecordMapper mapper = mock(ContextRecordMapper.class);
        MyBatisContextRepository repository =
                new MyBatisContextRepository(mapper, new ObjectMapper(), CLOCK);
        ContextRecordEntity current = record(0);
        ContextRecordEntity next = record(1);

        when(mapper.findByKey("conversation", "conv-1", "CONVERSATION", "conv-1", "QUERY"))
                .thenReturn(toRow(current));
        when(mapper.upsert(any(ContextRecordRow.class))).thenReturn(2);

        assertThatCode(() -> repository.upsertApproved(next, ExpectedContextVersion.version(0)))
                .doesNotThrowAnyException();
    }

    private static ContextRecordEntity record(long version) {
        return new ContextRecordEntity(
                "ctx-query",
                new ContextRecordKey(
                        new ContextOwnerRef("conversation", "conv-1"),
                        new ConversationScope("conv-1"),
                        RuntimeContextType.QUERY),
                AgentExecutionContracts.QUERY_CONTEXT,
                version,
                new ProtectedPayload(new byte[] {1}, "ACTIVE", new byte[] {1}, "stub"),
                "query.search",
                "inv-" + version,
                "employee",
                true,
                CLOCK.instant().plusSeconds(60));
    }

    private static ContextRecordRow toRow(ContextRecordEntity entity) {
        ContextRecordRow row = new ContextRecordRow();
        row.setContextId(entity.contextId());
        row.setOwnerType(entity.recordKey().owner().type());
        row.setOwnerId(entity.recordKey().owner().id());
        row.setScopeType("CONVERSATION");
        row.setScopeId(entity.recordKey().scope().scopeId());
        row.setContextType(entity.recordKey().contextType().name());
        row.setContractSchema(entity.contractRef().schema());
        row.setContractVersion(entity.contractRef().version());
        row.setRecordVersion(entity.recordVersion());
        row.setProtectedPayloadJson(
                "{\"ciphertext\":\"AQ==\",\"keyId\":\"ACTIVE\",\"nonce\":\"AQ==\",\"algorithmVersion\":\"stub\"}");
        row.setSourceCapabilityId(entity.sourceCapabilityId());
        row.setSourceInvocationId(entity.sourceInvocationId());
        row.setSourceDomain(entity.sourceDomain());
        row.setReadable(entity.readable());
        row.setExpiresAt(entity.expiresAt().atZone(CLOCK.getZone()).toLocalDateTime());
        row.setUpdatedAt(CLOCK.instant().atZone(CLOCK.getZone()).toLocalDateTime());
        return row;
    }
}
