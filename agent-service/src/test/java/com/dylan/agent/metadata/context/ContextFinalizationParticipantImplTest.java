package com.dylan.agent.metadata.context;

import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.enums.AggregateFunction;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.context.internal.ContextFinalizationParticipantImpl;
import com.dylan.agent.metadata.context.internal.ContextRecordEntity;
import com.dylan.agent.metadata.context.internal.ContextRepository;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ContextFinalizationParticipantImplTest {

    private static final Clock CLOCK =
            Clock.fixed(Instant.parse("2026-07-01T00:00:00Z"), ZoneOffset.UTC);

    @Test
    void persistsApprovedWritesInContextTypeOrderAndPassesExpectedVersion() {
        RecordingRepository repository = new RecordingRepository();
        ContextFinalizationParticipantImpl participant = participant(repository, Duration.ofHours(1));

        participant.persist(List.of(
                write("ctx-query", RuntimeContextType.QUERY, ExpectedContextVersion.version(3)),
                write("ctx-aggregate", RuntimeContextType.AGGREGATE, ExpectedContextVersion.absent())));

        assertThat(repository.records)
                .extracting(ContextRecordEntity::contextId)
                .containsExactly("ctx-aggregate", "ctx-query");
        assertThat(repository.expectedVersions)
                .extracting(ExpectedContextVersion::expectsAbsent)
                .containsExactly(true, false);
    }

    @Test
    void rejectsWritesPastCurrentStrictTtl() {
        ContextFinalizationParticipantImpl participant =
                participant(new RecordingRepository(), Duration.ofSeconds(10));

        ApprovedContextWrite write = new ApprovedContextWrite(
                "ctx-query",
                key(RuntimeContextType.QUERY),
                candidate(RuntimeContextType.QUERY),
                "query.search",
                "inv-1",
                "employee",
                CLOCK.instant().plusSeconds(11),
                ExpectedContextVersion.absent());

        assertThatThrownBy(() -> participant.persist(List.of(write)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("globalMaxContextTtl");
    }

    private ContextFinalizationParticipantImpl participant(
            RecordingRepository repository,
            Duration maxTtl) {
        return new ContextFinalizationParticipantImpl(
                repository,
                new PayloadJsonCodec(),
                new StubProtectedPayloadCodec(),
                new AgentSecuritySettingsRegistry(new AgentSecuritySettings(
                        maxTtl, Duration.ofMinutes(5), 10, "ACTIVE")),
                CLOCK);
    }

    private ApprovedContextWrite write(
            String contextId,
            RuntimeContextType type,
            ExpectedContextVersion expectedVersion) {
        return new ApprovedContextWrite(
                contextId,
                key(type),
                candidate(type),
                "query.search",
                "inv-1",
                "employee",
                CLOCK.instant().plusSeconds(30),
                expectedVersion);
    }

    private ContextRecordKey key(RuntimeContextType type) {
        return new ContextRecordKey(
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                type);
    }

    private ContextWriteCandidate candidate(RuntimeContextType type) {
        return new ContextWriteCandidate(
                type,
                new ContractRef("query_context", "v1"),
                payload(type));
    }

    private CapabilityContextPayload payload(RuntimeContextType type) {
        if (type == RuntimeContextType.QUERY) {
            return new QueryCapabilityContextPayload(null, List.of("name"), 1, 20);
        }
        AggregateMetricSpec metric = new AggregateMetricSpec();
        metric.setAlias("total");
        metric.setFunction(AggregateFunction.COUNT);
        return new AggregateCapabilityContextPayload(null, List.of(metric), List.of(), List.of(), 20);
    }

    private static final class RecordingRepository implements ContextRepository {
        private final List<ContextRecordEntity> records = new ArrayList<>();
        private final List<ExpectedContextVersion> expectedVersions = new ArrayList<>();

        @Override
        public void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion) {
            records.add(record);
            expectedVersions.add(expectedVersion);
        }

        @Override
        public void markConversationUnreadable(ConversationScope scope, Instant now) {
        }

        @Override
        public int deleteExpired(Instant cutoff, int limit) {
            return 0;
        }
    }

    private static final class StubProtectedPayloadCodec implements ProtectedPayloadCodec {
        @Override
        public ProtectedPayload encrypt(byte[] plaintext, PayloadProtectionContext context) {
            return new ProtectedPayload(plaintext, "ACTIVE", new byte[] {1}, "stub");
        }

        @Override
        public byte[] decrypt(ProtectedPayload payload, PayloadProtectionContext context) {
            return payload.ciphertext();
        }
    }
}
