package com.dylan.agent.testsupport;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.DocumentAgentPlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.response.DocumentAgentResultPayload;
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

import java.util.List;
import java.util.Optional;
import java.util.Set;

public final class KernelTestSupport {
    private KernelTestSupport() {
    }

    public static ResolvedRegistration resolvedQueryRegistration() {
        CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> registration =
                queryRegistration();
        CapabilityRegistry registry = new CapabilityRegistry(
                List.of(registration),
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(List.of(registration)),
                Set.of());
        return registry.resolve("query.search");
    }

    public static ResolvedRegistration resolvedDocumentSearchRegistration() {
        CapabilityRegistration<DocumentAgentPlan, DummyDocumentValidatedPlan, DocumentAgentResultPayload> registration =
                documentSearchRegistration();
        CapabilityRegistry registry = new CapabilityRegistry(
                List.of(registration),
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(List.of(registration)),
                Set.of(AdapterRole.DOCUMENT_RETRIEVABLE));
        return registry.resolve("document.search");
    }

    private static CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> queryRegistration() {
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
                (raw, ctx) -> new DummyValidatedPlan(),
                DummyValidatedPlan.class,
                (plan, ctx) -> HandlerResult.of(new QueryAgentResultPayload()),
                QueryAgentResultPayload.class);
    }

    private static CapabilityRegistration<DocumentAgentPlan, DummyDocumentValidatedPlan, DocumentAgentResultPayload>
    documentSearchRegistration() {
        CapabilityDefinition definition = CapabilityDefinition.builder()
                .capabilityId("document.search")
                .planKind(AgentPlanKind.DOCUMENT)
                .routingDescriptor(new CapabilityRoutingDescriptor("document", List.of("document"), List.of()))
                .domainMode(AgentDomainMode.REQUIRED)
                .adapterRole(AdapterRole.DOCUMENT_RETRIEVABLE)
                .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                .inputContract(AgentExecutionContracts.DOCUMENT_PLAN)
                .outputContract(AgentExecutionContracts.DOCUMENT_RESULT)
                .contextAccess(new ContextAccessDeclaration(List.of(), List.of()))
                .build();
        return new CapabilityRegistration<>(
                definition,
                DocumentAgentPlan.class,
                (raw, ctx) -> new DummyDocumentValidatedPlan(),
                DummyDocumentValidatedPlan.class,
                (plan, ctx) -> HandlerResult.of(new DocumentAgentResultPayload()),
                DocumentAgentResultPayload.class);
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
        public String capabilityId() { return "document.search"; }
        @Override
        public AgentPlanKind planKind() { return AgentPlanKind.DOCUMENT; }
        @Override
        public Optional<String> domain() { return Optional.of("company_policy"); }
    }
}
