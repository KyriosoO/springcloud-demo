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

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
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
import com.dylan.agent.metadata.context.internal.ContextBoundary;
import com.dylan.agent.metadata.context.internal.ContextRecordEntity;
import com.dylan.agent.metadata.context.internal.ContextRepository;
import com.dylan.agent.metadata.context.migration.ContextMigrationRegistry;
import com.dylan.agent.metadata.context.migration.QueryContextPayloadV10ToV12Migrator;
import com.dylan.agent.metadata.context.migration.QueryContextPayloadV11ToV12Migrator;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.context.request.ContextReadRequest;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.dylan.agent.shared.ref.AgentProfileRef;

class ContextBoundaryTest {
    @Test
    void approveDerivesOwnerScopeAndExpectedAbsentInsteadOfTrustingHandler() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(),
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
                repository, new PayloadJsonCodec(), new PlainCodec(),
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
    void approveRejectsLiveContextThatWasNotConsumedDuringPlanning() {
        RecordingRepository repository = new RecordingRepository(
                entity(4, true, MetadataTestSupport.NOW.plusSeconds(60)));
        ContextBoundary boundary = new ContextBoundary(
                repository, new PayloadJsonCodec(), new PlainCodec(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> boundary.approve(
                List.of(queryCandidate()),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(),
                        "employee", MetadataTestSupport.NOW)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("appeared after planning");
    }

    @Test
    void approveRejectsRetiredContextInsteadOfReopeningIt() {
        RecordingRepository repository = new RecordingRepository(
                entity(4, false, MetadataTestSupport.NOW.minusSeconds(1)));
        ContextBoundary boundary = new ContextBoundary(
                repository, new PayloadJsonCodec(), new PlainCodec(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> boundary.approve(
                List.of(queryCandidate()),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(),
                        "employee", MetadataTestSupport.NOW)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("must not be reopened");
    }

    @Test
    void approveRejectsDuplicateCandidateType() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> boundary.approve(
                List.of(queryCandidate(), queryCandidate()),
                new ContextApprovalRequest(handle(), nullRegistration(), executionScope(), List.of(),
                        "employee", MetadataTestSupport.NOW)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("duplicate context write candidate");
    }

    @Test
    void approveAcceptsDocumentContextWrite() {
        ContextBoundary boundary = new ContextBoundary(
                new NoopContextRepository(), new PayloadJsonCodec(), new PlainCodec(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var approved = boundary.approve(
                List.of(documentCandidate()),
                new ContextApprovalRequest(handle(), documentRegistration(), documentExecutionScope(), List.of(),
                        "tax_policy", MetadataTestSupport.NOW));

        assertThat(approved).singleElement().satisfies(write -> {
            assertThat(write.recordKey().contextType()).isEqualTo(RuntimeContextType.DOCUMENT);
            assertThat(write.sourceCapabilityId()).isEqualTo("document.answer");
            assertThat(write.sourceDomain()).contains("tax_policy");
            assertThat(write.candidate().payload()).isInstanceOf(DocumentCapabilityContextPayload.class);
        });
    }

    @Test
    void revalidateRejectsCurrentRecordVersionDrift() {
        ContextSnapshot snapshot = snapshot(3, MetadataTestSupport.NOW.plusSeconds(60));
        RecordingRepository repository = new RecordingRepository(entity(4, true, MetadataTestSupport.NOW.plusSeconds(60)));
        ContextBoundary boundary = new ContextBoundary(
                repository, new PayloadJsonCodec(), new PlainCodec(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        assertThatThrownBy(() -> boundary.revalidateAll(
                List.of(snapshot), handle(), nullRegistration(), executionScope()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("context snapshot is stale");
    }

    @Test
    void loadMigratesQueryContextV10ToV12() {
        assertMigratesLegacyQueryContext(AgentExecutionContracts.ref("QueryCapabilityContextPayload", "1.0.0"));
    }

    @Test
    void loadMigratesQueryContextV11ToV12() {
        assertMigratesLegacyQueryContext(AgentExecutionContracts.ref("QueryCapabilityContextPayload", "1.1.0"));
    }

    private void assertMigratesLegacyQueryContext(ContractRef sourceContract) {
        byte[] legacyJson = """
                {"filters":[],"page":1,"selectFields":["name"],"size":10}
                """.getBytes(java.nio.charset.StandardCharsets.UTF_8);
        ContextBoundary boundary = new ContextBoundary(
                new MigratingRepository(entity(1, true, MetadataTestSupport.NOW.plusSeconds(60), sourceContract, legacyJson)),
                new PayloadJsonCodec(),
                new PlainCodec(),
                new ContextMigrationRegistry(List.of(
                        new QueryContextPayloadV10ToV12Migrator(),
                        new QueryContextPayloadV11ToV12Migrator())),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        Optional<ContextSnapshot> loaded = boundary.load(new ContextReadRequest(
                "corr",
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                new ContextReadDeclaration(
                        RuntimeContextType.QUERY,
                        AgentExecutionContracts.QUERY_CONTEXT,
                        com.dylan.agent.api.context.QueryCapabilityContextPayload.class,
                        false,
                        java.util.Set.of("filters", "selectFields", "sorts", "page", "size")),
                ContextRuntimeViewTest.evidence()));

        assertThat(loaded).isPresent();
        assertThat(loaded.orElseThrow().storedContractRef()).isEqualTo(sourceContract);
        assertThat(loaded.orElseThrow().effectiveContractRef()).isEqualTo(AgentExecutionContracts.QUERY_CONTEXT);
        var payload = (com.dylan.agent.api.context.QueryCapabilityContextPayload) loaded.orElseThrow().payload();
        assertThat(payload.selectFields()).containsExactly("name");
        assertThat(payload.sorts()).isEmpty();
    }

    private InvocationHandle handle() {
        return InvocationHandle.forChat("inv-1",
                new ChatInvocationOrigin("conv-1", "turn-1"), "corr",
                new ExecutionSubjectRef("user", "u-1"), new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"), AgentProfileRef.of("agent-default", "profile-v1"),
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private ExecutionScope executionScope() {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create("user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                        "catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW, "perm", "perm-v1", "policy-v1",
                java.util.Set.of("query.search"), java.util.Set.of("employee"),
                java.util.Map.of(), java.util.Map.of(),
                java.util.Set.of(RuntimeContextType.QUERY), java.util.Set.of(RuntimeContextType.QUERY),
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective(100, 100, 10_000));
    }

    private ExecutionScope documentExecutionScope() {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create("user:u-1",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                        "catalog", "adapter", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW, "perm", "perm-v1", "policy-v1",
                java.util.Set.of("document.answer"), java.util.Set.of("tax_policy"),
                java.util.Map.of(), java.util.Map.of(),
                java.util.Set.of(RuntimeContextType.DOCUMENT), java.util.Set.of(RuntimeContextType.DOCUMENT),
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective(100, 100, 10_000));
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
                                .resourceLimitDeclaration(com.dylan.agent.kernel.resource.StandardResourceLimits.testDeclaration())
                                .resourceLimitConsumers(com.dylan.agent.kernel.resource.StandardResourceLimits.consumers("query.search"))
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
                com.dylan.agent.kernel.resource.StandardResourceLimits.registry(),
                java.util.Set.of());
        return registry.resolve("query.search");
    }

    private ResolvedRegistration documentRegistration() {
        CapabilityRegistration<DocumentAgentPlan, DummyDocumentValidatedPlan, DocumentAgentResultPayload> registration =
                new CapabilityRegistration<>(
                        CapabilityDefinition.builder()
                                .capabilityId("document.answer")
                                .planKind(AgentPlanKind.DOCUMENT)
                                .routingDescriptor(new CapabilityRoutingDescriptor("document", List.of("document"), List.of()))
                                .domainMode(AgentDomainMode.REQUIRED)
                                .adapterRole(AdapterRole.DOCUMENT_RETRIEVABLE)
                                .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                                .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                                .inputContract(AgentExecutionContracts.DOCUMENT_PLAN)
                                .outputContract(AgentExecutionContracts.DOCUMENT_RESULT)
                                .resourceLimitDeclaration(com.dylan.agent.kernel.resource.DocumentResourceLimits.declaration(
                                        com.dylan.agent.kernel.resource.DocumentResourceLimits.defaults()))
                                .resourceLimitConsumers(com.dylan.agent.kernel.resource.DocumentResourceLimits.consumers("document.answer"))
                                .contextAccess(new ContextAccessDeclaration(
                                        List.of(new ContextReadDeclaration(
                                                RuntimeContextType.DOCUMENT,
                                                AgentExecutionContracts.DOCUMENT_CONTEXT,
                                                DocumentCapabilityContextPayload.class,
                                                false,
                                                java.util.Set.of("operation", "domain", "materialType", "queryText", "filters",
                                                        "topK", "summaryScope"))),
                                        List.of(new ContextWriteDeclaration(
                                                RuntimeContextType.DOCUMENT,
                                                AgentExecutionContracts.DOCUMENT_CONTEXT,
                                                DocumentCapabilityContextPayload.class,
                                                Duration.ofDays(1),
                                                java.util.Set.of("operation", "domain", "materialType", "queryText", "filters",
                                                        "topK", "summaryScope")))))
                                .build(),
                        DocumentAgentPlan.class,
                        (raw, ctx) -> new DummyDocumentValidatedPlan(),
                        DummyDocumentValidatedPlan.class,
                        (plan, ctx) -> HandlerResult.of(new DocumentAgentResultPayload()),
                        DocumentAgentResultPayload.class);
        CapabilityRegistry registry = new CapabilityRegistry(
                List.of(registration),
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(List.of(registration)),
                new com.dylan.agent.kernel.resource.CapabilityResourceLimitRegistry(List.of(
                        new com.dylan.agent.kernel.resource.DocumentCapabilityResourceLimitContract())),
                java.util.Set.of(AdapterRole.DOCUMENT_RETRIEVABLE));
        return registry.resolve("document.answer");
    }

    private ContextWriteCandidate queryCandidate() {
        return new ContextWriteCandidate(RuntimeContextType.QUERY,
                AgentExecutionContracts.QUERY_CONTEXT,
                new com.dylan.agent.api.context.QueryCapabilityContextPayload(List.of(), List.of("name"), 1, 10));
    }

    private ContextWriteCandidate documentCandidate() {
        return new ContextWriteCandidate(RuntimeContextType.DOCUMENT,
                AgentExecutionContracts.DOCUMENT_CONTEXT,
                new DocumentCapabilityContextPayload(
                        "ANSWER", "tax_policy", "policy", "当前增值税率有哪些？",
                        List.of(), 5, "CUSTOM"));
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
        return entity(recordVersion, readable, expiresAt, AgentExecutionContracts.QUERY_CONTEXT, new byte[] {1});
    }

    private ContextRecordEntity entity(
            long recordVersion,
            boolean readable,
            Instant expiresAt,
            ContractRef contractRef,
            byte[] payload) {
        return new ContextRecordEntity(
                "ctx-existing",
                key(),
                contractRef,
                recordVersion,
                new ProtectedPayload(payload, "ACTIVE", new byte[] {1}, "stub"),
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

    private static final class MigratingRepository implements ContextRepository {
        private final ContextRecordEntity entity;

        private MigratingRepository(ContextRecordEntity entity) {
            this.entity = entity;
        }

        @Override
        public Optional<ContextRecordEntity> findCurrent(ContextRecordKey key, Instant now) {
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

    private record DummyDocumentValidatedPlan() implements ValidatedPlan {
        @Override
        public String capabilityId() { return "document.answer"; }

        @Override
        public AgentPlanKind planKind() { return AgentPlanKind.DOCUMENT; }

        @Override
        public Optional<String> domain() { return Optional.of("tax_policy"); }
    }
}
