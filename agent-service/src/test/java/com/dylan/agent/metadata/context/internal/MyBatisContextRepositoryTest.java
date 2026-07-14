package com.dylan.agent.metadata.context.internal;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;

import org.junit.jupiter.api.Test;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Update;

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
    void upsertApprovedUsesVersionCheckedCompareAndSet() {
        ContextRecordMapper mapper = mock(ContextRecordMapper.class);
        MyBatisContextRepository repository =
                new MyBatisContextRepository(mapper, new ObjectMapper(), CLOCK);
        ContextRecordEntity current = record(0);
        ContextRecordEntity next = record(1);

        when(mapper.updateIfVersion(any(ContextRecordRow.class), org.mockito.ArgumentMatchers.eq(0L)))
                .thenReturn(1);

        assertThatCode(() -> repository.upsertApproved(next, ExpectedContextVersion.version(0)))
                .doesNotThrowAnyException();
    }

    @Test
    void mapperCasCannotReopenRetiredRecordAndCleanupOrderIsStable() throws Exception {
        Update update = ContextRecordMapper.class
                .getMethod("updateIfVersion", ContextRecordRow.class, long.class)
                .getAnnotation(Update.class);
        Delete delete = ContextRecordMapper.class
                .getMethod("deleteExpired", java.time.LocalDateTime.class, int.class)
                .getAnnotation(Delete.class);

        assertThat(String.join(" ", update.value()))
                .contains("record_version = #{expectedCurrentVersion} AND readable = 1");
        assertThat(String.join(" ", delete.value()))
                .contains("ORDER BY expires_at ASC, context_id ASC LIMIT #{limit}");
    }

    @Test
    void cleanupLimitIsBounded() {
        MyBatisContextRepository repository = new MyBatisContextRepository(
                mock(ContextRecordMapper.class), new ObjectMapper(), CLOCK);

        assertThatThrownBy(() -> repository.deleteExpired(CLOCK.instant(), 1001))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("between 1 and 1000");
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
        row.setContractNamespace(entity.contractRef().namespace());
        row.setContractName(entity.contractRef().name());
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
