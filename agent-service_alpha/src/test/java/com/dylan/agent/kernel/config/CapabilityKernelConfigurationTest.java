package com.dylan.agent.kernel.config;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainRoutingProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainSchema;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.QueryAgentResultPayload;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.handler.HandlerResult;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.CapabilityRegistrationValidator;
import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainAvailabilitySnapshot;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Set;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CapabilityKernelConfigurationTest {

    private final CapabilityKernelConfiguration configuration = new CapabilityKernelConfiguration();

    @Test
    void contractRegistryRejectsEmptyRegistrationSet() {
        assertThatThrownBy(() -> configuration.contractRegistry(List.of()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("at least one CapabilityRegistration");
    }

    @Test
    void buildsContractRegistryAndCapabilityRegistryFromRegistrations() {
        var registration = queryRegistration();
        var contracts = configuration.contractRegistry(List.of(registration));
        var registry = configuration.capabilityRegistry(
                List.of(registration),
                contracts,
                com.dylan.agent.kernel.resource.StandardResourceLimits.registry(),
                new CapabilityRegistrationValidator(),
                new FakeDomainMetadataPort(Set.of()));

        assertThat(contracts.require(AgentExecutionContracts.QUERY_PLAN).javaType())
                .isEqualTo(QueryAgentPlan.class);
        assertThat(registry.resolve("query.search").registration()).isSameAs(registration);
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

    private record FakeDomainMetadataPort(Set<AdapterRole> knownRoles) implements DomainMetadataPort {
        @Override
        public DomainMetadataEvidence validateReferences(
                DomainMetadataReferenceSet refs,
                Instant absoluteDeadline) {
            throw new UnsupportedOperationException();
        }

        @Override
        public DomainAvailabilitySnapshot availability(
                Set<AdapterRole> roles,
                PlanningEffectiveScope scope,
                Instant absoluteDeadline) {
            throw new UnsupportedOperationException();
        }

        @Override
        public void assertCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<RuntimeDomainRoutingProjection> routeProjection(
                Set<String> domains,
                PlanningEffectiveScope scope,
                DomainMetadataEvidence expected,
                Instant absoluteDeadline) {
            throw new UnsupportedOperationException();
        }

        @Override
        public RuntimeDomainSchema planSchema(
                AdapterRole role,
                String domain,
                PlanningEffectiveScope scope,
                DomainMetadataEvidence expected,
                Instant absoluteDeadline) {
            throw new UnsupportedOperationException();
        }

        @Override
        public com.dylan.agent.kernel.port.model.DomainExecutionResolution resolveExecution(
                AdapterRole role,
                String domain,
                ExecutionScope scope,
                DomainMetadataEvidence expected,
                Instant absoluteDeadline) {
            throw new UnsupportedOperationException();
        }
    }
}
