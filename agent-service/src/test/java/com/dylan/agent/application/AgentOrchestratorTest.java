package com.dylan.agent.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.invocation.model.CancellationToken;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationState;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.lifecycle.ExecutionLifecycleService;
import com.dylan.agent.lifecycle.model.FinalizedInvocationResult;
import com.dylan.agent.lifecycle.model.InvocationResponseType;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.PlanningService;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningCancellation;
import com.dylan.agent.planning.model.PlanningCancellationException;
import com.dylan.agent.planning.model.PlanningCommand;
import com.dylan.agent.planning.model.PlanningFailure;
import com.dylan.agent.planning.model.PlanningFailureException;
import com.dylan.agent.planning.model.PlanningStage;
import com.dylan.agent.planning.model.ResolvedClarification;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

@DisplayName("AgentOrchestrator")
class AgentOrchestratorTest {

    private static final Instant NOW = Instant.parse("2026-07-02T04:00:00Z");
    private static final Clock CLOCK = Clock.fixed(NOW, ZoneOffset.UTC);
    private static final AgentUserContext USER = new AgentUserContext("u-1", Set.of("agent:viewer"));

    private StartChatCommandFactory startChatCommandFactory;
    private ExecutionLifecycleService lifecycleService;
    private ConversationService conversationService;
    private PlanningCommandFactory planningCommandFactory;
    private PlanningService planningService;
    private AgentChatResponseAssembler responseAssembler;
    private AgentProperties properties;
    private AgentOrchestrator orchestrator;
    private InvocationHandle handle;
    private StartChatCommand startCommand;
    private PlanningCommand planningCommand;

    @BeforeEach
    void setUp() {
        startChatCommandFactory = mock(StartChatCommandFactory.class);
        lifecycleService = mock(ExecutionLifecycleService.class);
        conversationService = mock(ConversationService.class);
        planningCommandFactory = mock(PlanningCommandFactory.class);
        planningService = mock(PlanningService.class);
        responseAssembler = mock(AgentChatResponseAssembler.class);
        properties = properties();
        orchestrator = new AgentOrchestrator(
                startChatCommandFactory,
                lifecycleService,
                conversationService,
                planningCommandFactory,
                planningService,
                responseAssembler,
                CLOCK,
                properties);

        handle = handle();
        startCommand = new StartChatCommand(
                USER,
                "conv-1",
                "查员工",
                handle.agentProfileRef(),
                NOW.plusSeconds(12));
        planningCommand = new PlanningCommand(
                handle,
                startCommand.message(),
                List.of(),
                handle.agentProfileRef(),
                null);
    }

    @Test
    void executableResultUsesConfiguredDeadlineHistoryLimitAndSameCancellationToken() {
        AgentChatRequest request = request();
        ExecutablePlanningResult executable = mock(ExecutablePlanningResult.class);
        FinalizedInvocationResult finalized = finalized(InvocationResponseType.SUCCESS);
        AgentChatResponse expected = response(AgentResponseType.RESULT);
        ArgumentCaptor<Instant> deadline = ArgumentCaptor.forClass(Instant.class);
        ArgumentCaptor<CancellationToken> planningToken = ArgumentCaptor.forClass(CancellationToken.class);
        ArgumentCaptor<CancellationToken> executionToken = ArgumentCaptor.forClass(CancellationToken.class);
        when(startChatCommandFactory.create(eq(USER), eq(request), deadline.capture())).thenReturn(startCommand);
        when(lifecycleService.startChat(startCommand)).thenReturn(handle);
        when(conversationService.loadRecentTurns(handle, 7)).thenReturn(List.of());
        when(planningCommandFactory.create(handle, "查员工", List.of())).thenReturn(planningCommand);
        when(planningService.plan(eq(planningCommand), planningToken.capture())).thenReturn(executable);
        when(lifecycleService.executeAndFinalize(eq(handle), eq(executable), executionToken.capture()))
                .thenReturn(finalized);
        when(responseAssembler.fromFinalizedResult(finalized)).thenReturn(expected);

        AgentChatResponse actual = orchestrator.chat(USER, request);

        assertThat(actual).isSameAs(expected);
        assertThat(deadline.getValue()).isEqualTo(NOW.plusSeconds(12));
        assertThat(executionToken.getValue()).isSameAs(planningToken.getValue());
        verify(lifecycleService, never()).finalizeClarification(any(), any());
        verify(lifecycleService, never()).finalizePlanningFailure(any(), any());
        verify(lifecycleService, never()).finalizeCancelled(any(), any());
    }

    @Test
    void clarificationResultFinalizesWithoutExecution() {
        AgentChatRequest request = request();
        ResolvedClarification clarification = mock(ResolvedClarification.class);
        FinalizedInvocationResult finalized = finalized(InvocationResponseType.CLARIFY);
        AgentChatResponse expected = response(AgentResponseType.CLARIFY);
        when(startChatCommandFactory.create(eq(USER), eq(request), any())).thenReturn(startCommand);
        when(lifecycleService.startChat(startCommand)).thenReturn(handle);
        when(conversationService.loadRecentTurns(handle, 7)).thenReturn(List.of());
        when(planningCommandFactory.create(handle, "查员工", List.of())).thenReturn(planningCommand);
        when(planningService.plan(eq(planningCommand), any())).thenReturn(clarification);
        when(lifecycleService.finalizeClarification(handle, clarification)).thenReturn(finalized);
        when(responseAssembler.fromFinalizedResult(finalized)).thenReturn(expected);

        AgentChatResponse actual = orchestrator.chat(USER, request);

        assertThat(actual).isSameAs(expected);
        verify(lifecycleService, never()).executeAndFinalize(any(), any(), any());
        verify(lifecycleService, never()).finalizePlanningFailure(any(), any());
        verify(lifecycleService, never()).finalizeCancelled(any(), any());
    }

    @Test
    void planningFailureIsFinalizedThroughLifecycle() {
        AgentChatRequest request = request();
        PlanningFailure failure = new PlanningFailure(
                "req-1",
                PlanningStage.ROUTE,
                KernelErrorCode.RUNTIME_UNAVAILABLE,
                "runtime-route",
                null,
                null,
                List.of());
        FinalizedInvocationResult finalized = finalized(InvocationResponseType.FAILURE);
        AgentChatResponse expected = response(AgentResponseType.ERROR);
        when(startChatCommandFactory.create(eq(USER), eq(request), any())).thenReturn(startCommand);
        when(lifecycleService.startChat(startCommand)).thenReturn(handle);
        when(conversationService.loadRecentTurns(handle, 7)).thenReturn(List.of());
        when(planningCommandFactory.create(handle, "查员工", List.of())).thenReturn(planningCommand);
        when(planningService.plan(eq(planningCommand), any())).thenThrow(new PlanningFailureException(failure));
        when(lifecycleService.finalizePlanningFailure(handle, failure)).thenReturn(finalized);
        when(responseAssembler.fromFinalizedResult(finalized)).thenReturn(expected);

        AgentChatResponse actual = orchestrator.chat(USER, request);

        assertThat(actual).isSameAs(expected);
        verify(lifecycleService, never()).executeAndFinalize(any(), any(), any());
        verify(lifecycleService, never()).finalizeClarification(any(), any());
    }

    @Test
    void planningCancellationIsFinalizedThroughLifecycle() {
        AgentChatRequest request = request();
        PlanningCancellation cancellation = PlanningCancellation.beforePlanning(
                "req-1",
                KernelErrorCode.CANCELLED);
        FinalizedInvocationResult finalized = finalized(InvocationResponseType.CANCELLED);
        AgentChatResponse expected = response(AgentResponseType.ERROR);
        when(startChatCommandFactory.create(eq(USER), eq(request), any())).thenReturn(startCommand);
        when(lifecycleService.startChat(startCommand)).thenReturn(handle);
        when(conversationService.loadRecentTurns(handle, 7)).thenReturn(List.of());
        when(planningCommandFactory.create(handle, "查员工", List.of())).thenReturn(planningCommand);
        when(planningService.plan(eq(planningCommand), any())).thenThrow(new PlanningCancellationException(cancellation));
        when(lifecycleService.finalizeCancelled(handle, cancellation)).thenReturn(finalized);
        when(responseAssembler.fromFinalizedResult(finalized)).thenReturn(expected);

        AgentChatResponse actual = orchestrator.chat(USER, request);

        assertThat(actual).isSameAs(expected);
        verify(lifecycleService, never()).executeAndFinalize(any(), any(), any());
        verify(lifecycleService, never()).finalizeClarification(any(), any());
        verify(lifecycleService, never()).finalizePlanningFailure(any(), any());
    }

    private static AgentProperties properties() {
        AgentProperties properties = new AgentProperties();
        AgentProperties.RuntimeProperties runtime = new AgentProperties.RuntimeProperties();
        runtime.setReadTimeout(Duration.ofSeconds(12));
        properties.setRuntime(runtime);
        AgentProperties.ConversationProperties conversation = new AgentProperties.ConversationProperties();
        conversation.setRecentTurnLimit(7);
        properties.setConversation(conversation);
        return properties;
    }

    private static AgentChatRequest request() {
        AgentChatRequest request = new AgentChatRequest();
        request.setConversationId("conv-1");
        request.setMessage("查员工");
        return request;
    }

    private static InvocationHandle handle() {
        return InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "req-1",
                new ExecutionSubjectRef("user", "u-1"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                AgentProfileRef.of("agent-default", "profile-v1"),
                NOW.plusSeconds(12));
    }

    private static FinalizedInvocationResult finalized(InvocationResponseType responseType) {
        return FinalizedInvocationResult.builder()
                .invocationId("inv-1")
                .origin(new ChatInvocationOrigin("conv-1", "turn-1"))
                .state(responseType == InvocationResponseType.CANCELLED
                        ? InvocationState.CANCELLED
                        : responseType == InvocationResponseType.FAILURE
                        ? InvocationState.FAILED
                        : InvocationState.COMPLETED)
                .responseType(responseType)
                .safeMessage("safe")
                .build();
    }

    private static AgentChatResponse response(AgentResponseType type) {
        AgentChatResponse response = new AgentChatResponse();
        response.setConversationId("conv-1");
        response.setTurnId("turn-1");
        response.setType(type);
        response.setMessage("safe");
        response.setSummary("safe");
        return response;
    }
}
