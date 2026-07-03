package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;

import org.junit.jupiter.api.Test;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.definition.ContextWriteDeclaration;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.context.internal.ContextBoundary;
import com.dylan.agent.metadata.context.internal.ContextRecordEntity;
import com.dylan.agent.metadata.context.internal.ContextRepository;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.dylan.agent.shared.ref.AgentProfileRef;

class ContextBoundaryTest {
    @Test
    void approveDerivesOwnerScopeAndExpectedAbsentInsteadOfTrustingHandler() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var approved = boundary.approve(
                List.of(queryCandidate()),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(),
                        "employee", MetadataTestSupport.NOW));

        assertThat(approved).singleElement().satisfies(write -> {
            assertThat(write.recordKey().owner().id()).isEqualTo("conv-1");
            assertThat(write.expectedVersion().expectsAbsent()).isTrue();
            assertThat(write.sourceDomain()).contains("employee");
        });
    }

    @Test
    void approveUsesExistingRecordVersionWhenSnapshotWasNotConsumed() {
        RecordingRepository repository = new RecordingRepository(entity(4, true, MetadataTestSupport.NOW.minusSeconds(1)));
        ContextBoundary boundary = new ContextBoundary(
                repository, new PayloadJsonCodec(), new PlainCodec(), settings(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var approved = boundary.approve(
                List.of(queryCandidate()),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(),
                        "employee", MetadataTestSupport.NOW));

        assertThat(approved).singleElement().satisfies(write -> {
            assertThat(write.contextId()).isEqualTo("ctx-existing");
            assertThat(write.expectedVersion().expectsAbsent()).isFalse();
            assertThat(write.expectedVersion().targetVersion()).isEqualTo(5);
        });
    }

    @Test
    void approveRejectsDuplicateCandidateType() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(), settings(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> boundary.approve(
                List.of(queryCandidate(), queryCandidate()),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(),
                        "employee", MetadataTestSupport.NOW)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("duplicate context write candidate");
    }

    @Test
    void revalidateRejectsCurrentRecordVersionDrift() {
        ContextSnapshot snapshot = snapshot(3, MetadataTestSupport.NOW.plusSeconds(60));
        RecordingRepository repository = new RecordingRepository(entity(4, true, MetadataTestSupport.NOW.plusSeconds(60)));
        ContextBoundary boundary = new ContextBoundary(
                repository, new PayloadJsonCodec(), new PlainCodec(), settings(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> boundary.revalidateAll(
                List.of(snapshot), handle(), nullRegistration(), executionScope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("context snapshot is stale");
    }

    private InvocationHandle handle() {
        return InvocationHandle.create("inv-1", InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"), "corr",
                new ExecutionSubjectRef("user", "u-1"), new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"), AgentProfileRef.of("agent-default", "profile-v1"),
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private ExecutionScope executionScope() {
        return new ExecutionScope("user:u-1",
                new com.dylan.agent.metadata.domain.port.DomainMetadataEvidence(
                        "catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW, "perm", "perm-v1", "policy-v1",
                java.util.Set.of("query.search"), java.util.Set.of("employee"),
                java.util.Map.of(), java.util.Map.of(),
                java.util.Set.of(RuntimeContextType.QUERY), java.util.Set.of(RuntimeContextType.QUERY),
                java.time.Duration.ofSeconds(30), 1, 100, 10_000);
    }

    private com.dylan.agent.kernel.registration.ResolvedRegistration nullRegistration() {
        CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> registration =
                new CapabilityRegistration<>(
                        CapabilityDefinition.builder()
                                .capabilityId("query.search")
                                .planKind(AgentPlanKind.QUERY)
                                .routingDescriptor(new CapabilityRoutingDescriptor("query", List.of("query"), List.of()))
                                .domainMode(AgentDomainMode.NONE)
                                .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                                .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                                .inputContract(AgentExecutionContracts.QUERY_PLAN)
                                .outputContract(AgentExecutionContracts.QUERY_RESULT)
                                .contextAccess(new ContextAccessDeclaration(
                                        List.of(new ContextReadDeclaration(
                                                RuntimeContextType.QUERY,
                                                AgentExecutionContracts.QUERY_CONTEXT,
                                                com.dylan.agent.api.context.QueryCapabilityContextPayload.class,
                                                false,
                                                java.util.Set.of("filters", "selectFields", "page", "size"))),
                                        List.of(new ContextWriteDeclaration(
                                                RuntimeContextType.QUERY,
                                                AgentExecutionContracts.QUERY_CONTEXT,
                                                com.dylan.agent.api.context.QueryCapabilityContextPayload.class,
                                                Duration.ofDays(1),
                                                java.util.Set.of("filters", "selectFields", "page", "size")))))
                                .build(),
                        QueryAgentPlan.class,
                        (raw, ctx) -> new DummyValidatedPlan(),
                        DummyValidatedPlan.class,
                        (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()),
                        QueryAgentResultPayload.class);
        CapabilityRegistry registry = new CapabilityRegistry(
                List.of(registration),
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(List.of(registration)),
                java.util.Set.of());
        return registry.resolve("query.search");
    }

    private ContextWriteCandidate queryCandidate() {
        return new ContextWriteCandidate(RuntimeContextType.QUERY,
                AgentExecutionContracts.QUERY_CONTEXT,
                new com.dylan.agent.api.context.QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10));
    }

    private ContextSnapshot snapshot(long recordVersion, Instant expiresAt) {
        return new ContextSnapshot(
                "ctx-existing",
                "corr",
                key(),
                "query.search",
                "inv-previous",
                "employee",
                AgentExecutionContracts.QUERY_CONTEXT,
                AgentExecutionContracts.QUERY_CONTEXT,
                recordVersion,
                expiresAt,
                "bundle-v1",
                "policy-v1",
                "perm",
                null,
                ExpectedContextVersion.version(recordVersion),
                new com.dylan.agent.api.context.QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10));
    }

    private ContextRecordEntity entity(long recordVersion, boolean readable, Instant expiresAt) {
        return new ContextRecordEntity(
                "ctx-existing",
                key(),
                AgentExecutionContracts.QUERY_CONTEXT,
                recordVersion,
                new ProtectedPayload(new byte[] {1}, "ACTIVE", new byte[] {1}, "stub"),
                "query.search",
                "inv-previous",
                "employee",
                readable,
                expiresAt);
    }

    private ContextRecordKey key() {
        return new ContextRecordKey(
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                RuntimeContextType.QUERY);
    }

    private AgentSecuritySettingsRegistry settings() {
        return new AgentSecuritySettingsRegistry(
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ZERO, 10, "ACTIVE"));
    }

    private static final class RecordingRepository implements ContextRepository {
        private final ContextRecordEntity entity;

        private RecordingRepository(ContextRecordEntity entity) {
            this.entity = entity;
        }

        @Override
        public Optional<ContextRecordEntity> findByKey(ContextRecordKey key) {
            return Optional.of(entity);
        }

        @Override
        public void upsertApproved(ContextRecordEntity record, ExpectedContextVersion expectedVersion) {
        }

        @Override
        public void markConversationUnreadable(ConversationScope scope, Instant now) {
        }

        @Override
        public int deleteExpired(Instant cutoff, int limit) {
            return 0;
        }
    }

    private record DummyValidatedPlan() implements ValidatedPlan {
        @Override
        public String capabilityId() { return "query.search"; }

        @Override
        public AgentPlanKind planKind() { return AgentPlanKind.QUERY; }

        @Override
        public Optional<String> domain() { return Optional.empty(); }
    }
}
