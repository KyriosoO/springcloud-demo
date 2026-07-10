package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainSchema;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.metadata.MetadataTestSupport;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.catalog.AvailableCapability;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.profile.internal.ProfileBehaviorProjectionBoundary;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.EffectiveProfile;
import com.dylan.agent.planning.model.PlanningCommand;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;
import com.dylan.agent.testsupport.KernelTestSupport;
import com.dylan.agent.testsupport.RuntimeContractTestSupport;

import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;

class RuntimePlanningRequestFactoryTest {

    @Test
    void clampsDocumentPlanSchemaToDocumentRetrievalBudget() {
        AgentProperties properties = DomainMetadataTestSupport.agentProperties();
        properties.getDocument().getRetrieval().setDefaultSize(5);
        properties.getDocument().getRetrieval().setMaxSize(30);
        DomainMetadataPort domainMetadataPort = mock(DomainMetadataPort.class);
        RuntimeDomainSchema schema = new RuntimeDomainSchema();
        schema.setDomain("policy_document");
        schema.setDefaultSize(100);
        schema.setMaxSize(100);
        when(domainMetadataPort.planSchema(
                eq(AdapterRole.DOCUMENT_RETRIEVABLE),
                eq("policy_document"),
                any(),
                any(),
                any()))
                .thenReturn(schema);
        RuntimePlanningRequestFactory factory = new RuntimePlanningRequestFactory(
                domainMetadataPort,
                mock(ProfileBehaviorProjectionBoundary.class),
                properties);

        var request = factory.planRequest(
                command(),
                evidence(),
                routeDecision(),
                KernelTestSupport.resolvedDocumentSearchRegistration(),
                List.of());

        assertThat(request.getDomainSchema().getMaxSize()).isEqualTo(30);
        assertThat(request.getDomainSchema().getDefaultSize()).isEqualTo(5);
    }

    private static PlanningCommand command() {
        InvocationHandle handle = InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "req-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                MetadataTestSupport.NOW.plusSeconds(60));
        return new PlanningCommand(
                handle,
                "查询政策文档",
                List.of(),
                handle.agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL);
    }

    private static PlanningAuthorizationEvidence evidence() {
        AgentProfileVersionKey profileKey = new AgentProfileVersionKey("agent-default", "profile-v1");
        EffectiveProfile profile = new EffectiveProfile(
                profileKey,
                "policy-v1",
                Set.of("document.search"),
                Set.of("policy_document"),
                Set.of(RuntimeContextType.DOCUMENT),
                Set.of(RuntimeContextType.DOCUMENT),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                100,
                100,
                10_000);
        return new PlanningAuthorizationEvidence(
                "req-1",
                "user:u-1",
                profileKey,
                "bundle-v1",
                "digest-v1",
                "policy-v1",
                "perm",
                "perm-v1",
                DelegationConstraintRef.CHAT_ALL,
                profile,
                new PlanningEffectiveScope(
                        Set.of("document.search"),
                        Set.of("policy_document"),
                        Map.of(),
                        Set.of(),
                        Set.of(),
                        AgentCapabilityRiskLevel.READ_ONLY,
                        AgentCapabilityExecutionMode.IMMEDIATE,
                        Duration.ofSeconds(30),
                        1,
                        100,
                        100,
                        10_000),
                domainEvidence(),
                MetadataTestSupport.NOW,
                MetadataTestSupport.NOW.plusSeconds(60));
    }

    private static ValidatedRouteDecision routeDecision() {
        RouteDecision decision = new RouteDecision();
        decision.setRequestId("req-1");
        decision.setCapabilityId("document.search");
        decision.setDomain("policy_document");
        decision.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.ROUTE));
        AvailableCapability capability = new AvailableCapability(
                "document.search",
                AgentPlanKind.DOCUMENT,
                AgentDomainMode.REQUIRED,
                new CapabilityRoutingDescriptor("document", List.of("document"), List.of()),
                Set.of("policy_document"),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                100,
                100,
                10_000,
                "document-search");
        return new ValidatedRouteDecision(decision, capability, Optional.of("policy_document"));
    }

    private static DomainMetadataEvidence domainEvidence() {
        return new DomainMetadataEvidence(
                "catalog-v1",
                "adapter-v1",
                "availability-v1",
                MetadataTestSupport.NOW);
    }
}
