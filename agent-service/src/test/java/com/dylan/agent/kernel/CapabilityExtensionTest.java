package com.dylan.agent.kernel;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
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
import com.dylan.agent.kernel.validator.ValidatedPlan;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class CapabilityExtensionTest {

    @Test
    void registersSecondCapabilityOfSamePlanKindWithoutPlanKindRoutingApi() {
        List<CapabilityRegistration<?, ?, ?>> registrations = List.of(
                queryRegistration("query.search"),
                queryRegistration("query.preview"));

        CapabilityRegistry registry = new CapabilityRegistry(
                registrations,
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(registrations),
                Set.of());

        assertThat(registry.resolve("query.search").registration().definition().capabilityId())
                .isEqualTo("query.search");
        assertThat(registry.resolve("query.preview").registration().definition().capabilityId())
                .isEqualTo("query.preview");
        assertThat(registry.coverageByPlanKind().get(AgentPlanKind.QUERY))
                .containsExactlyInAnyOrder("query.search", "query.preview");
    }

    private CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> queryRegistration(
            String capabilityId) {
        CapabilityDefinition definition = CapabilityDefinition.builder()
                .capabilityId(capabilityId)
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
                (raw, ctx) -> new DummyValidatedPlan(capabilityId, AgentPlanKind.QUERY),
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
