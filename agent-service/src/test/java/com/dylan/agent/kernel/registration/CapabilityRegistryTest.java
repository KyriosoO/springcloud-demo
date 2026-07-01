package com.dylan.agent.kernel.registration;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AggregateAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.kernel.core.ExecutionValidationContext;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import org.junit.jupiter.api.Test;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CapabilityRegistryTest {

    @Test
    void resolvesOnlyByCapabilityId() {
        var registration = queryRegistration("query.search", AgentPlanKind.QUERY, QueryAgentPlan.class);
        var registry = registry(List.of(registration));

        assertThat(registry.resolve("query.search").capabilityId()).isEqualTo("query.search");
        assertThatThrownBy(() -> registry.resolve("missing.capability"))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(registry.coverageByPlanKind()).containsKey(AgentPlanKind.QUERY);
    }

    @Test
    void rejectsDuplicateCapabilityId() {
        var left = queryRegistration("query.search", AgentPlanKind.QUERY, QueryAgentPlan.class);
        var right = queryRegistration("query.search", AgentPlanKind.QUERY, QueryAgentPlan.class);

        assertThatThrownBy(() -> registry(List.of(left, right)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("duplicate");
    }

    @Test
    void rejectsRawPlanKindMismatch() {
        var bad = registration("query.search", AgentPlanKind.QUERY, AggregateAgentPlan.class,
                AgentExecutionContracts.AGGREGATE_PLAN);

        assertThatThrownBy(() -> registry(List.of(bad)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("planKind/raw subtype mismatch");
    }

    @Test
    void contractRegistryPinsRuntimeSchemaRefs() {
        var registration = queryRegistration("query.search", AgentPlanKind.QUERY, QueryAgentPlan.class);
        ContractRegistry contracts = ContractRegistry.from(List.of(registration));

        assertThat(contracts.runtimeSchemaRef(AgentExecutionContracts.QUERY_PLAN))
                .isEqualTo("#/components/schemas/QueryAgentPlan");
        assertThatThrownBy(() -> contracts.runtimeSchemaRef(AgentExecutionContracts.QUERY_RESULT))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsInvalidDomainModeRole() {
        var registration = registration(
                "query.search",
                AgentPlanKind.QUERY,
                QueryAgentPlan.class,
                AgentExecutionContracts.QUERY_PLAN,
                AgentDomainMode.REQUIRED,
                AdapterRole.QUERYABLE);

        assertThatThrownBy(() -> registry(List.of(registration), Set.of()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("unknown adapterRole");
    }

    @Test
    void doesNotExposeMutableRegistrationCollections() {
        var registration = queryRegistration("query.search", AgentPlanKind.QUERY, QueryAgentPlan.class);
        var registry = registry(List.of(registration));

        assertThatThrownBy(() -> registry.registrations().clear())
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> registry.capabilityIds().add("query.other"))
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> registry.coverageByPlanKind().put(AgentPlanKind.AGGREGATE, List.of("aggregate.compute")))
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> registry.coverageByPlanKind().get(AgentPlanKind.QUERY).add("query.other"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    private CapabilityRegistry registry(Collection<CapabilityRegistration<?, ?, ?>> registrations) {
        return registry(registrations, Set.of());
    }

    private CapabilityRegistry registry(Collection<CapabilityRegistration<?, ?, ?>> registrations, Set<AdapterRole> knownRoles) {
        ContractRegistry contracts = ContractRegistry.from(registrations);
        return new CapabilityRegistry(registrations, new CapabilityRegistrationValidator(), contracts, knownRoles);
    }

    private <R extends com.dylan.agent.api.contract.runtime.plan.AgentPlan>
    CapabilityRegistration<R, DummyValidatedPlan, QueryAgentResultPayload> queryRegistration(
            String id, AgentPlanKind planKind, Class<R> rawType) {
        return registration(id, planKind, rawType, AgentExecutionContracts.QUERY_PLAN);
    }

    private <R extends com.dylan.agent.api.contract.runtime.plan.AgentPlan>
    CapabilityRegistration<R, DummyValidatedPlan, QueryAgentResultPayload> registration(
            String id,
            AgentPlanKind planKind,
            Class<R> rawType,
            com.dylan.agent.api.contract.common.ContractRef inputContract) {
        return registration(id, planKind, rawType, inputContract, AgentDomainMode.NONE, null);
    }

    private <R extends com.dylan.agent.api.contract.runtime.plan.AgentPlan>
    CapabilityRegistration<R, DummyValidatedPlan, QueryAgentResultPayload> registration(
            String id,
            AgentPlanKind planKind,
            Class<R> rawType,
            com.dylan.agent.api.contract.common.ContractRef inputContract,
            AgentDomainMode domainMode,
            AdapterRole adapterRole) {
        CapabilityDefinition definition = CapabilityDefinition.builder()
                .capabilityId(id)
                .planKind(planKind)
                .routingDescriptor(new CapabilityRoutingDescriptor("query", List.of("query"), List.of()))
                .domainMode(domainMode)
                .adapterRole(adapterRole)
                .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                .inputContract(inputContract)
                .outputContract(AgentExecutionContracts.QUERY_RESULT)
                .contextAccess(new ContextAccessDeclaration(List.of(), List.of()))
                .build();
        return new CapabilityRegistration<>(
                definition,
                rawType,
                (raw, ctx) -> new DummyValidatedPlan(id, planKind),
                DummyValidatedPlan.class,
                (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()),
                QueryAgentResultPayload.class);
    }

    private record DummyValidatedPlan(String capabilityId, AgentPlanKind planKind)
            implements ValidatedPlan {
        @Override
        public Optional<String> domain() {
            return Optional.empty();
        }
    }
}
