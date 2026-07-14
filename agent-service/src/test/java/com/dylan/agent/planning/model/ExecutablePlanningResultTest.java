package com.dylan.agent.planning.model;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ExecutablePlanningResultTest {

    private static final Instant NOW = Instant.parse("2026-07-01T00:00:00Z");
    private static final Instant DEADLINE = NOW.plusSeconds(30);

    @Test
    void acceptsConsistentResolvedRegistrationAndRawPlan() {
        ResolvedRegistration resolved = registry().resolve("query.search");

        ExecutablePlanningResult result = baseBuilder(resolved)
                .domain(" employee ")
                .build();

        assertThat(result.capabilityId()).isEqualTo("query.search");
        assertThat(result.domain()).contains("employee");
        assertThat(result.planKind()).isEqualTo(AgentPlanKind.QUERY);
        assertThat(result.rawPlan()).isInstanceOf(QueryAgentPlan.class);
    }

    @Test
    void rejectsCapabilityIdPlanKindOrRawPlanMismatch() {
        ResolvedRegistration resolved = registry().resolve("query.search");

        assertThatThrownBy(() -> baseBuilder(resolved)
                .capabilityId("query.other")
                .build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("capabilityId");

        assertThatThrownBy(() -> baseBuilder(resolved)
                .planKind(AgentPlanKind.AGGREGATE)
                .build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("planKind");

        assertThatThrownBy(() -> baseBuilder(resolved)
                .rawPlan(new AggregateAgentPlan())
                .build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("rawPlan");
    }

    @Test
    void rejectsWrongAuditOperationOrder() {
        ResolvedRegistration resolved = registry().resolve("query.search");

        assertThatThrownBy(() -> baseBuilder(resolved)
                .routeAudit(reported(RuntimeOperationType.PLAN))
                .build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("routeAudit");

        assertThatThrownBy(() -> baseBuilder(resolved)
                .planAudit(reported(RuntimeOperationType.ROUTE))
                .build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("planAudit");
    }

    private ExecutablePlanningResult.Builder baseBuilder(ResolvedRegistration resolved) {
        return ExecutablePlanningResult.builder()
                .invocationId("inv-1")
                .requestCorrelationId("corr-1")
                .capabilityId("query.search")
                .planKind(AgentPlanKind.QUERY)
                .resolvedRegistration(resolved)
                .rawPlan(new QueryAgentPlan())
                .authorizationSnapshot(authorizationSnapshot())
                .contextSnapshots(List.of())
                .routeAudit(reported(RuntimeOperationType.ROUTE))
                .planAudit(reported(RuntimeOperationType.PLAN))
                .absoluteDeadline(DEADLINE);
    }

    private CapabilityRegistry registry() {
        CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> registration =
                queryRegistration();
        List<CapabilityRegistration<?, ?, ?>> registrations = List.of(registration);
        return new CapabilityRegistry(
                registrations,
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(registrations),
                com.dylan.agent.kernel.resource.StandardResourceLimits.registry(),
                Set.of());
    }

    private CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> queryRegistration() {
        CapabilityDefinition definition = CapabilityDefinition.builder()
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
                .contextAccess(new ContextAccessDeclaration(List.of(), List.of()))
                .build();
        return new CapabilityRegistration<>(
                definition,
                QueryAgentPlan.class,
                (raw, ctx) -> new DummyValidatedPlan(),
                DummyValidatedPlan.class,
                (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()),
                QueryAgentResultPayload.class);
    }

    private AuthorizationSnapshot authorizationSnapshot() {
        return com.dylan.agent.testsupport.AuthorizationSnapshotTestFactory.create(
                "auth-1",
                "user:u-1",
                "profile-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of(),
                Map.of(),
                Map.of(),
                NOW,
                null,
                com.dylan.agent.kernel.resource.StandardResourceLimits.testEffective());
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

    private record DummyValidatedPlan() implements ValidatedPlan {
        @Override
        public String capabilityId() {
            return "query.search";
        }

        @Override
        public AgentPlanKind planKind() {
            return AgentPlanKind.QUERY;
        }

        @Override
        public Optional<String> domain() {
            return Optional.empty();
        }
    }
}
