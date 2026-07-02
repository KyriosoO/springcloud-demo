package com.dylan.agent.kernel.core;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.kernel.port.ContextApprovalPort;
import com.dylan.agent.kernel.port.ContextExecutionPort;
import com.dylan.agent.kernel.port.DomainExecutionPort;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.invocation.model.ExecutionStage;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.dylan.agent.shared.ref.AgentProfileRef;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class ExecutionCoreTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");
    private static final Instant DEADLINE = NOW.plusSeconds(60);
    private static final Clock CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);

    @Test
    void validatorFailureReturnsPlanValidationFailureAndDoesNotInvokeLaterStages() {
        AtomicBoolean handlerCalled = new AtomicBoolean(false);
        AtomicBoolean resultSecurityCalled = new AtomicBoolean(false);
        AtomicBoolean contextApprovalCalled = new AtomicBoolean(false);

        var registration = queryRegistration(
                (raw, ctx) -> {
                    throw new IllegalArgumentException("invalid raw plan");
                },
                (plan, ctx) -> {
                    handlerCalled.set(true);
                    return HandlerResult.of(new QueryAgentResultPayload());
                });
        var registry = registry(registration);

        ExecutionCore core = new ExecutionCore(
                authorizationPort(),
                (snapshots, handle, resolved, scope) -> { },
                failingDomainPort(),
                (candidates, request) -> {
                    contextApprovalCalled.set(true);
                    return List.of();
                },
                (candidate, outputContract, scope) -> {
                    resultSecurityCalled.set(true);
                    return null;
                },
                CLOCK);

        ExecutionOutcome outcome = core.execute(command(registry.resolve("query.search")));

        assertThat(outcome).isInstanceOf(ExecutionFailure.class);
        ExecutionFailure failure = (ExecutionFailure) outcome;
        assertThat(failure.stage()).isEqualTo(ExecutionStage.PLAN_VALIDATION);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.PLAN_VALIDATION_FAILED);
        assertThat(handlerCalled).isFalse();
        assertThat(resultSecurityCalled).isFalse();
        assertThat(contextApprovalCalled).isFalse();
    }

    @Test
    void deadlineBeforeValidatorReturnsCancellationFailureAndDoesNotInvokeLaterStages() {
        AtomicBoolean validatorCalled = new AtomicBoolean(false);
        AtomicBoolean handlerCalled = new AtomicBoolean(false);
        AtomicBoolean resultSecurityCalled = new AtomicBoolean(false);
        AtomicBoolean contextApprovalCalled = new AtomicBoolean(false);

        var registration = queryRegistration(
                (raw, ctx) -> {
                    validatorCalled.set(true);
                    return new DummyValidatedPlan("query.search", AgentPlanKind.QUERY);
                },
                (plan, ctx) -> {
                    handlerCalled.set(true);
                    return HandlerResult.of(new QueryAgentResultPayload());
                });
        var registry = registry(registration);

        ExecutionCore core = new ExecutionCore(
                authorizationPort(),
                (snapshots, handle, resolved, scope) -> { },
                failingDomainPort(),
                (candidates, request) -> {
                    contextApprovalCalled.set(true);
                    return List.of();
                },
                (candidate, outputContract, scope) -> {
                    resultSecurityCalled.set(true);
                    return null;
                },
                new SequenceClock(NOW, DEADLINE));

        ExecutionOutcome outcome = core.execute(command(registry.resolve("query.search")));

        assertThat(outcome).isInstanceOf(ExecutionFailure.class);
        ExecutionFailure failure = (ExecutionFailure) outcome;
        assertThat(failure.stage()).isEqualTo(ExecutionStage.CANCELLATION_DEADLINE);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.DEADLINE_EXCEEDED);
        assertThat(failure.cancelled()).isTrue();
        assertThat(validatorCalled).isFalse();
        assertThat(handlerCalled).isFalse();
        assertThat(resultSecurityCalled).isFalse();
        assertThat(contextApprovalCalled).isFalse();
    }

    @Test
    void nullSecuredResultFailsBeforeContextApproval() {
        AtomicBoolean contextApprovalCalled = new AtomicBoolean(false);

        var registration = queryRegistration(
                (raw, ctx) -> new DummyValidatedPlan("query.search", AgentPlanKind.QUERY),
                (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()));
        var registry = registry(registration);

        ExecutionCore core = new ExecutionCore(
                authorizationPort(),
                (snapshots, handle, resolved, scope) -> { },
                failingDomainPort(),
                (candidates, request) -> {
                    contextApprovalCalled.set(true);
                    return List.of();
                },
                (candidate, outputContract, scope) -> null,
                CLOCK);

        ExecutionOutcome outcome = core.execute(command(registry.resolve("query.search")));

        assertThat(outcome).isInstanceOf(ExecutionFailure.class);
        ExecutionFailure failure = (ExecutionFailure) outcome;
        assertThat(failure.stage()).isEqualTo(ExecutionStage.RESULT_SECURITY);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.RESULT_SECURITY_FAILED);
        assertThat(contextApprovalCalled).isFalse();
    }

    @Test
    void deadlineAfterHandlerDiscardsLateCandidateBeforeResultSecurity() {
        AtomicBoolean handlerCalled = new AtomicBoolean(false);
        AtomicBoolean resultSecurityCalled = new AtomicBoolean(false);
        AtomicBoolean contextApprovalCalled = new AtomicBoolean(false);

        var registration = queryRegistration(
                (raw, ctx) -> new DummyValidatedPlan("query.search", AgentPlanKind.QUERY),
                (plan, ctx) -> {
                    handlerCalled.set(true);
                    return HandlerResult.of(new QueryAgentResultPayload());
                });
        var registry = registry(registration);

        ExecutionCore core = new ExecutionCore(
                authorizationPort(),
                (snapshots, handle, resolved, scope) -> { },
                failingDomainPort(),
                (candidates, request) -> {
                    contextApprovalCalled.set(true);
                    return List.of();
                },
                (candidate, outputContract, scope) -> {
                    resultSecurityCalled.set(true);
                    return null;
                },
                new SequenceClock(NOW, NOW, NOW, DEADLINE));

        ExecutionOutcome outcome = core.execute(command(registry.resolve("query.search")));

        assertThat(outcome).isInstanceOf(ExecutionFailure.class);
        ExecutionFailure failure = (ExecutionFailure) outcome;
        assertThat(failure.stage()).isEqualTo(ExecutionStage.CANCELLATION_DEADLINE);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.DEADLINE_EXCEEDED);
        assertThat(failure.cancelled()).isTrue();
        assertThat(handlerCalled).isTrue();
        assertThat(resultSecurityCalled).isFalse();
        assertThat(contextApprovalCalled).isFalse();
    }

    @Test
    void securedResultBindingMismatchFailsBeforeContextApproval() {
        AtomicBoolean contextApprovalCalled = new AtomicBoolean(false);

        var registration = queryRegistration(
                (raw, ctx) -> new DummyValidatedPlan("query.search", AgentPlanKind.QUERY),
                (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()));
        var registry = registry(registration);

        ExecutionCore core = new ExecutionCore(
                authorizationPort(),
                (snapshots, handle, resolved, scope) -> { },
                failingDomainPort(),
                (candidates, request) -> {
                    contextApprovalCalled.set(true);
                    return List.of();
                },
                (candidate, outputContract, scope) -> new SecuredResult(
                        new ContractRef("OtherResult", "1.0.0"),
                        "{}".getBytes(java.nio.charset.StandardCharsets.UTF_8),
                        "safe",
                        "safe"),
                CLOCK);

        ExecutionOutcome outcome = core.execute(command(registry.resolve("query.search")));

        assertThat(outcome).isInstanceOf(ExecutionFailure.class);
        ExecutionFailure failure = (ExecutionFailure) outcome;
        assertThat(failure.stage()).isEqualTo(ExecutionStage.RESULT_SECURITY);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.RESULT_SECURITY_FAILED);
        assertThat(contextApprovalCalled).isFalse();
    }

    @Test
    void nullApprovedWritesFailsContextApproval() {
        var registration = queryRegistration(
                (raw, ctx) -> new DummyValidatedPlan("query.search", AgentPlanKind.QUERY),
                (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()));
        var registry = registry(registration);

        ExecutionCore core = new ExecutionCore(
                authorizationPort(),
                (snapshots, handle, resolved, scope) -> { },
                failingDomainPort(),
                (candidates, request) -> null,
                (candidate, outputContract, scope) -> new SecuredResult(
                        outputContract,
                        "{}".getBytes(java.nio.charset.StandardCharsets.UTF_8),
                        "safe",
                        "safe"),
                CLOCK);

        ExecutionOutcome outcome = core.execute(command(registry.resolve("query.search")));

        assertThat(outcome).isInstanceOf(ExecutionFailure.class);
        ExecutionFailure failure = (ExecutionFailure) outcome;
        assertThat(failure.stage()).isEqualTo(ExecutionStage.CONTEXT_APPROVAL);
        assertThat(failure.errorCode()).isEqualTo(KernelErrorCode.CONTEXT_WRITE_CONFLICT);
    }

    private CapabilityRegistry registry(CapabilityRegistration<?, ?, ?> registration) {
        List<CapabilityRegistration<?, ?, ?>> registrations = List.of(registration);
        return new CapabilityRegistry(
                registrations,
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(registrations),
                Set.of());
    }

    private CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> queryRegistration(
            com.dylan.agent.kernel.validator.CapabilityPlanValidator<QueryAgentPlan, DummyValidatedPlan> validator,
            com.dylan.agent.kernel.handler.CapabilityHandler<DummyValidatedPlan, QueryAgentResultPayload> handler) {
        CapabilityDefinition definition = CapabilityDefinition.builder()
                .capabilityId("query.search")
                .planKind(AgentPlanKind.QUERY)
                .routingDescriptor(new CapabilityRoutingDescriptor("query", List.of("query"), List.of()))
                .domainMode(AgentDomainMode.NONE)
                .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                .inputContract(AgentExecutionContracts.QUERY_PLAN)
                .outputContract(AgentExecutionContracts.QUERY_RESULT)
                .contextAccess(new ContextAccessDeclaration(List.of(), List.of()))
                .build();
        return new CapabilityRegistration<>(
                definition,
                QueryAgentPlan.class,
                validator,
                DummyValidatedPlan.class,
                handler,
                QueryAgentResultPayload.class);
    }

    private ExecutionCommand command(com.dylan.agent.kernel.registration.ResolvedRegistration resolved) {
        return new ExecutionCommand(handle(), planningResult(resolved), new CancellationSource().token());
    }

    private InvocationHandle handle() {
        return InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "corr-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "v1"),
                DEADLINE);
    }

    private ExecutablePlanningResult planningResult(
            com.dylan.agent.kernel.registration.ResolvedRegistration resolved) {
        return ExecutablePlanningResult.builder()
                .requestCorrelationId("corr-1")
                .capabilityId("query.search")
                .planKind(AgentPlanKind.QUERY)
                .resolvedRegistration(resolved)
                .rawPlan(new QueryAgentPlan())
                .authorizationSnapshot(authorizationSnapshot())
                .contextSnapshots(List.of())
                .routeAudit(reported(RuntimeOperationType.ROUTE))
                .planAudit(reported(RuntimeOperationType.PLAN))
                .absoluteDeadline(DEADLINE)
                .build();
    }

    private AuthorizationSnapshot authorizationSnapshot() {
        return new AuthorizationSnapshot(
                "auth-1",
                "user:u-1",
                "profile-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of(),
                Map.of(),
                NOW);
    }

    private AuthorizationExecutionPort authorizationPort() {
        return (snapshot, handle) -> new ExecutionScope(
                "user:u-1",
                domainEvidence(),
                NOW,
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of(),
                Map.of(),
                Map.of(),
                Duration.ofSeconds(30),
                1,
                100,
                10_000);
    }

    private DomainMetadataEvidence domainEvidence() {
        return new DomainMetadataEvidence(
                "catalog-v1",
                "adapter-v1",
                "availability-v1",
                NOW);
    }

    private DomainExecutionPort failingDomainPort() {
        return request -> {
            throw new AssertionError("domain port must not be called for NONE domain mode");
        };
    }

    private PlanningOperationAudit reported(RuntimeOperationType operation) {
        RuntimeOperationMetadata metadata = new RuntimeOperationMetadata();
        metadata.setOperation(operation);
        metadata.setProviderAttempts(1);
        metadata.setRepairAttempts(0);
        metadata.setRepairDurationMs(0L);
        metadata.setTotalDurationMs(1L);
        metadata.setTerminationReason(RuntimeTerminationReason.COMPLETED);
        metadata.setDeadlineReached(false);
        metadata.setRepairLimitReached(false);
        return PlanningOperationAudit.reported(metadata, 1L, PlanningOperationTermination.OUTCOME_RECEIVED);
    }

    private record DummyValidatedPlan(String capabilityId, AgentPlanKind planKind)
            implements ValidatedPlan {
        @Override
        public Optional<String> domain() {
            return Optional.empty();
        }
    }

    private static final class SequenceClock extends Clock {
        private final List<Instant> instants;
        private final AtomicInteger calls = new AtomicInteger();

        private SequenceClock(Instant first, Instant... rest) {
            this.instants = java.util.stream.Stream.concat(
                    java.util.stream.Stream.of(first),
                    java.util.Arrays.stream(rest))
                    .toList();
        }

        @Override
        public ZoneId getZone() {
            return ZoneOffset.UTC;
        }

        @Override
        public Clock withZone(ZoneId zone) {
            return this;
        }

        @Override
        public Instant instant() {
            int index = calls.getAndIncrement();
            return index < instants.size()
                    ? instants.get(index)
                    : instants.get(instants.size() - 1);
        }
    }
}
