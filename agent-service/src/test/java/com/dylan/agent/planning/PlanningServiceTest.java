package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.clarification.DomainChoiceArgs;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.PlanRequest;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.client.AgentRuntimeErrorMapper;
import com.dylan.agent.client.RuntimeOperationException;
import com.dylan.agent.client.RuntimeOperationFailure;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.MetadataTestSupport;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.ExecutionBudget;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.authorization.request.CapabilityScopeSelection;
import com.dylan.agent.metadata.catalog.AvailableCapability;
import com.dylan.agent.metadata.catalog.AvailableCapabilitySnapshot;
import com.dylan.agent.metadata.catalog.CapabilityCatalog;
import com.dylan.agent.metadata.context.port.ContextPlanningPort;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningCancellationException;
import com.dylan.agent.planning.model.PlanningCommand;
import com.dylan.agent.planning.model.PlanningFailureException;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.dylan.agent.planning.model.ResolvedClarification;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.KernelTestSupport;
import com.dylan.agent.testsupport.RuntimeContractTestSupport;

import java.time.Clock;
import java.time.Duration;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

class PlanningServiceTest {

    private static final Clock CLOCK = Clock.fixed(MetadataTestSupport.NOW, ZoneOffset.UTC);

    private AuthorizationPlanningPort authorizationPlanningPort;
    private CapabilityCatalog capabilityCatalog;
    private RuntimePlanningRequestFactory requestFactory;
    private AgentRuntimeClient runtimeClient;
    private CapabilitySelectionResolver selectionResolver;
    private ContextPlanningPort contextPlanningPort;
    private PlanningService service;

    @BeforeEach
    void setUp() {
        authorizationPlanningPort = mock(AuthorizationPlanningPort.class);
        capabilityCatalog = mock(CapabilityCatalog.class);
        requestFactory = mock(RuntimePlanningRequestFactory.class);
        runtimeClient = mock(AgentRuntimeClient.class);
        selectionResolver = mock(CapabilitySelectionResolver.class);
        contextPlanningPort = mock(ContextPlanningPort.class);
        service = new PlanningService(
                authorizationPlanningPort,
                capabilityCatalog,
                requestFactory,
                runtimeClient,
                new RouteOutcomeValidator(),
                selectionResolver,
                contextPlanningPort,
                new PlanOutcomeValidator(),
                new PlanningClarificationResolver(),
                new AgentRuntimeErrorMapper(),
                CLOCK);
    }

    @Test
    void returnsExecutablePlanningResultForRouteAndPlanSuccess() {
        ResolvedRegistration registration = KernelTestSupport.resolvedQueryRegistration();
        PlanningAuthorizationEvidence evidence = evidence();
        AvailableCapabilitySnapshot available = available(registration);
        AuthorizationSnapshot authorizationSnapshot = authorizationSnapshot();
        when(authorizationPlanningPort.capture(any())).thenReturn(evidence);
        when(capabilityCatalog.available(evidence)).thenReturn(available);
        when(requestFactory.routeRequest(any(), any(), any())).thenReturn(new RouteRequest());
        when(runtimeClient.route(any())).thenReturn(routeDecision());
        when(selectionResolver.resolve(any(), any())).thenReturn(registration);
        when(requestFactory.planRequest(any(), any(), any(), any(), any())).thenReturn(new PlanRequest());
        when(runtimeClient.plan(any())).thenReturn(executablePlan());
        when(authorizationPlanningPort.freezeCapabilityScope(any(), any())).thenReturn(authorizationSnapshot);

        ExecutablePlanningResult result = (ExecutablePlanningResult) service.plan(command(), token());

        assertThat(result.capabilityId()).isEqualTo("query.search");
        assertThat(result.rawPlan()).isInstanceOf(QueryAgentPlan.class);
        assertThat(result.authorizationSnapshot()).isSameAs(authorizationSnapshot);
        assertThat(result.routeAudit().operation()).isEqualTo(RuntimeOperationType.ROUTE);
        assertThat(result.planAudit().operation()).isEqualTo(RuntimeOperationType.PLAN);
        InOrder order = inOrder(runtimeClient, authorizationPlanningPort);
        order.verify(runtimeClient).route(any());
        order.verify(runtimeClient).plan(any());
        order.verify(authorizationPlanningPort).freezeCapabilityScope(any(), any(CapabilityScopeSelection.class));
    }

    @Test
    void routeClarificationDoesNotCallPlan() {
        ResolvedRegistration registration = KernelTestSupport.resolvedQueryRegistration();
        PlanningAuthorizationEvidence evidence = evidence();
        AvailableCapabilitySnapshot available = available(registration);
        when(authorizationPlanningPort.capture(any())).thenReturn(evidence);
        when(capabilityCatalog.available(evidence)).thenReturn(available);
        when(requestFactory.routeRequest(any(), any(), any())).thenReturn(new RouteRequest());
        when(runtimeClient.route(any())).thenReturn(routeClarification());

        ResolvedClarification result = (ResolvedClarification) service.plan(command(), token());

        assertThat(result.stage()).isEqualTo(ResolvedClarification.ClarificationStage.ROUTE);
        assertThat(result.reasonCode()).isEqualTo(ClarificationReasonCode.DOMAIN_REQUIRED);
        assertThat(result.safeQuestion()).contains("employee");
        verifyNoInteractions(selectionResolver, contextPlanningPort);
    }

    @Test
    void planRuntimeFailureKeepsReportedRouteAudit() {
        ResolvedRegistration registration = KernelTestSupport.resolvedQueryRegistration();
        PlanningAuthorizationEvidence evidence = evidence();
        AvailableCapabilitySnapshot available = available(registration);
        when(authorizationPlanningPort.capture(any())).thenReturn(evidence);
        when(capabilityCatalog.available(evidence)).thenReturn(available);
        when(requestFactory.routeRequest(any(), any(), any())).thenReturn(new RouteRequest());
        when(runtimeClient.route(any())).thenReturn(routeDecision());
        when(selectionResolver.resolve(any(), any())).thenReturn(registration);
        when(requestFactory.planRequest(any(), any(), any(), any(), any())).thenReturn(new PlanRequest());
        when(runtimeClient.plan(any())).thenThrow(new RuntimeOperationException(
                RuntimeOperationType.PLAN,
                RuntimeOperationFailure.PROVIDER,
                PlanningOperationAudit.notReported(
                        RuntimeOperationType.PLAN,
                        3L,
                        PlanningOperationTermination.TRANSPORT_FAILURE),
                "runtime-plan-provider",
                null));

        assertThatThrownBy(() -> service.plan(command(), token()))
                .isInstanceOf(PlanningFailureException.class)
                .satisfies(error -> {
                    PlanningFailureException ex = (PlanningFailureException) error;
                    assertThat(ex.failure().operationAudits()).hasSize(2);
                    assertThat(ex.failure().operationAudits().get(0).operation()).isEqualTo(RuntimeOperationType.ROUTE);
                    assertThat(ex.failure().operationAudits().get(1).operation()).isEqualTo(RuntimeOperationType.PLAN);
                });
    }

    @Test
    void cancelledTokenStopsBeforeAuthorizationCapture() {
        CancellationSource source = new CancellationSource();
        source.cancel(KernelErrorCode.CANCELLED);

        assertThatThrownBy(() -> service.plan(command(), source.token()))
                .isInstanceOf(PlanningCancellationException.class)
                .satisfies(error -> {
                    PlanningCancellationException ex = (PlanningCancellationException) error;
                    assertThat(ex.cancellation().errorCode()).isEqualTo(KernelErrorCode.CANCELLED);
                });
        verifyNoInteractions(authorizationPlanningPort, capabilityCatalog, runtimeClient);
    }

    @Test
    void routeRuntimeDeadlineBecomesPlanningCancellationWithEvidenceRefs() {
        ResolvedRegistration registration = KernelTestSupport.resolvedQueryRegistration();
        PlanningAuthorizationEvidence evidence = evidence();
        AvailableCapabilitySnapshot available = available(registration);
        when(authorizationPlanningPort.capture(any())).thenReturn(evidence);
        when(capabilityCatalog.available(evidence)).thenReturn(available);
        when(requestFactory.routeRequest(any(), any(), any())).thenReturn(new RouteRequest());
        when(runtimeClient.route(any())).thenThrow(new RuntimeOperationException(
                RuntimeOperationType.ROUTE,
                RuntimeOperationFailure.DEADLINE,
                PlanningOperationAudit.notReported(
                        RuntimeOperationType.ROUTE,
                        3L,
                        PlanningOperationTermination.CANCELLED),
                "runtime-route-deadline",
                null));

        assertThatThrownBy(() -> service.plan(command(), token()))
                .isInstanceOf(PlanningCancellationException.class)
                .satisfies(error -> {
                    PlanningCancellationException ex = (PlanningCancellationException) error;
                    assertThat(ex.cancellation().errorCode()).isEqualTo(KernelErrorCode.DEADLINE_EXCEEDED);
                    assertThat(ex.cancellation().authorizationEvidenceRef()).contains(evidence().evidenceDigest());
                    assertThat(ex.cancellation().domainMetadataEvidenceRef()).contains(domainEvidence().safeRef());
                    assertThat(ex.cancellation().operationAudits()).hasSize(1);
                });
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
                "查员工",
                List.of(),
                handle.agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL);
    }

    private static com.dylan.agent.invocation.model.CancellationToken token() {
        return new CancellationSource().token();
    }

    private static PlanningAuthorizationEvidence evidence() {
        var bundle = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        var profile = bundle.requireProfile(new AgentProfileVersionKey("agent-default", "profile-v1"));
        return new PlanningAuthorizationEvidence(
                "req-1",
                "user:u-1",
                profile.key(),
                bundle.bundleVersion(),
                bundle.bundleDigest(),
                "policy-v1",
                "perm",
                "perm-v1",
                DelegationConstraintRef.CHAT_ALL,
                new EffectiveProfileCalculator().compute(profile, bundle.activePolicy()),
                new com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope(
                        Set.of("query.search"),
                        Set.of("employee"),
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

    private static AvailableCapabilitySnapshot available(ResolvedRegistration registration) {
        return new AvailableCapabilitySnapshot(
                "req-1",
                "auth-digest",
                domainEvidence(),
                List.of(new AvailableCapability(
                        "query.search",
                        AgentPlanKind.QUERY,
                        AgentDomainMode.NONE,
                        new CapabilityRoutingDescriptor("query", List.of("query"), List.of()),
                        Set.of(),
                        AgentCapabilityRiskLevel.READ_ONLY,
                        AgentCapabilityExecutionMode.IMMEDIATE,
                        Duration.ofSeconds(30),
                        1,
                        100,
                        100,
                        10_000,
                        registration.registrationIdentity())),
                MetadataTestSupport.NOW);
    }

    private static DomainMetadataEvidence domainEvidence() {
        return new DomainMetadataEvidence("catalog-v1", "adapter-v1", "availability-v1", MetadataTestSupport.NOW);
    }

    private static RouteDecision routeDecision() {
        RouteDecision decision = new RouteDecision();
        decision.setRequestId("req-1");
        decision.setCapabilityId("query.search");
        decision.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.ROUTE));
        return decision;
    }

    private static ClarificationRequired routeClarification() {
        DomainChoiceArgs args = new DomainChoiceArgs();
        args.setDomains(List.of("employee"));
        ClarificationRequired clarification = new ClarificationRequired();
        clarification.setRequestId("req-1");
        clarification.setReasonCode(ClarificationReasonCode.DOMAIN_REQUIRED);
        clarification.setArgs(args);
        clarification.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.ROUTE));
        return clarification;
    }

    private static ExecutablePlan executablePlan() {
        QueryAgentPlan plan = new QueryAgentPlan();
        AgentQuerySpec query = new AgentQuerySpec();
        query.setSelectFields(List.of("chineseName"));
        plan.setQuery(query);

        ExecutablePlan executable = new ExecutablePlan();
        executable.setRequestId("req-1");
        executable.setPlan(plan);
        executable.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.PLAN));
        return executable;
    }

    private static AuthorizationSnapshot authorizationSnapshot() {
        return new AuthorizationSnapshot(
                "auth-req-1",
                "user:u-1",
                "profile-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of(),
                Map.of(),
                Map.of(),
                MetadataTestSupport.NOW,
                domainEvidence(),
                new ExecutionBudget(1, 100, 10_000));
    }
}
