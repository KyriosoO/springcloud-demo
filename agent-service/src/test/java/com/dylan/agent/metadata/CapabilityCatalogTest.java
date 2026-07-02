package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Clock;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
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
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.catalog.CapabilityCatalog;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class CapabilityCatalogTest {
    @Test
    void requiredDomainCapabilityIsProjectedOnlyWhenD04AvailabilityAllowsDomain() {
        CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> registration = registration();
        CapabilityRegistry registry = new CapabilityRegistry(
                List.of(registration),
                new CapabilityRegistrationValidator(),
                ContractRegistry.from(List.of(registration)),
                Set.of(AdapterRole.QUERYABLE));
        CapabilityCatalog catalog = new CapabilityCatalog(
                registry,
                DomainMetadataTestSupport.domainMetadataPort(),
                Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC));

        var snapshot = catalog.available(evidence());

        assertThat(snapshot.capabilityIds()).containsExactly("query.search");
        assertThat(snapshot.getRequired("query.search").allowedDomains()).containsExactly("employee");
    }

    private PlanningAuthorizationEvidence evidence() {
        var bundle = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        var profile = bundle.requireProfile(new AgentProfileVersionKey("agent-default", "profile-v1"));
        return new PlanningAuthorizationEvidence(
                "corr", "user:u-1", profile.key(), bundle.bundleVersion(), bundle.bundleDigest(),
                "policy-v1", "perm", "perm-v1", DelegationConstraintRef.CHAT_ALL,
                new EffectiveProfileCalculator().compute(profile, bundle.activePolicy()),
                new PlanningEffectiveScope(
                        Set.of("query.search"), Set.of("employee"), Map.of(),
                        Set.of(), Set.of(), AgentCapabilityRiskLevel.READ_ONLY,
                        AgentCapabilityExecutionMode.IMMEDIATE,
                        java.time.Duration.ofSeconds(30), 1, 100, 100, 10_000),
                new DomainMetadataEvidence("catalog-test", "adapter-reg-test", "availability", MetadataTestSupport.NOW),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private CapabilityRegistration<QueryAgentPlan, DummyValidatedPlan, QueryAgentResultPayload> registration() {
        CapabilityDefinition definition = CapabilityDefinition.builder()
                .capabilityId("query.search")
                .planKind(AgentPlanKind.QUERY)
                .routingDescriptor(new CapabilityRoutingDescriptor("query", List.of("query"), List.of()))
                .domainMode(AgentDomainMode.REQUIRED)
                .adapterRole(AdapterRole.QUERYABLE)
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

    private record DummyValidatedPlan() implements ValidatedPlan {
        @Override
        public String capabilityId() { return "query.search"; }
        @Override
        public AgentPlanKind planKind() { return AgentPlanKind.QUERY; }
        @Override
        public java.util.Optional<String> domain() { return java.util.Optional.of("employee"); }
    }
}
