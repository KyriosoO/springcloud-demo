package com.dylan.agent.application;

import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.exception.AgentInternalException;
import com.dylan.agent.invocation.model.CancellationSource;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.lifecycle.ExecutionLifecycleService;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.PlanningService;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningCancellationException;
import com.dylan.agent.planning.model.PlanningFailureException;
import com.dylan.agent.planning.model.PlanningResult;
import com.dylan.agent.planning.model.ResolvedClarification;
import org.springframework.stereotype.Component;

import java.time.Clock;
import java.util.Objects;

/**
 * D03 CHAT 入口适配器。
 *
 * <p>只协调入口归一化、生命周期、规划、执行和响应组装。
 * Runtime 调用、处理器路由、授权和持久化细节都留在各自边界之后。</p>
 */
@Component
public class AgentOrchestrator {

    private final StartChatCommandFactory startChatCommandFactory;
    private final ExecutionLifecycleService lifecycleService;
    private final ConversationService conversationService;
    private final PlanningCommandFactory planningCommandFactory;
    private final PlanningService planningService;
    private final AgentChatResponseAssembler responseAssembler;
    private final Clock clock;
    private final AgentProperties properties;

    public AgentOrchestrator(StartChatCommandFactory startChatCommandFactory,
                             ExecutionLifecycleService lifecycleService,
                             ConversationService conversationService,
                             PlanningCommandFactory planningCommandFactory,
                             PlanningService planningService,
                             AgentChatResponseAssembler responseAssembler,
                             Clock clock,
                             AgentProperties properties) {
        this.startChatCommandFactory = Objects.requireNonNull(startChatCommandFactory);
        this.lifecycleService = Objects.requireNonNull(lifecycleService);
        this.conversationService = Objects.requireNonNull(conversationService);
        this.planningCommandFactory = Objects.requireNonNull(planningCommandFactory);
        this.planningService = Objects.requireNonNull(planningService);
        this.responseAssembler = Objects.requireNonNull(responseAssembler);
        this.clock = Objects.requireNonNull(clock);
        this.properties = Objects.requireNonNull(properties);
    }

    public AgentChatResponse chat(AgentUserContext userContext, AgentChatRequest request) {
        StartChatCommand startCommand = startChatCommandFactory.create(userContext, request, absoluteDeadline());
        InvocationHandle handle = lifecycleService.startChat(startCommand);
        CancellationSource cancellationSource = new CancellationSource();
        try {
            var history = conversationService.loadRecentTurns(handle, properties.getConversation().getRecentTurnLimit());
            var planningCommand = planningCommandFactory.create(
                    handle,
                    startCommand.message(),
                    history,
                    startCommand.requestedProfile(),
                    startCommand.materialType());
            PlanningResult planningResult = planningService.plan(planningCommand, cancellationSource.token());
            if (planningResult instanceof ResolvedClarification clarification) {
                return responseAssembler.fromFinalizedResult(
                        lifecycleService.finalizeClarification(handle, clarification));
            }
            if (planningResult instanceof ExecutablePlanningResult executable) {
                return responseAssembler.fromFinalizedResult(
                        lifecycleService.executeAndFinalize(
                                handle,
                                executable,
                                cancellationSource.token()));
            }
            throw new AgentInternalException("系统内部错误，请稍后重试。", null);
        } catch (PlanningFailureException ex) {
            return responseAssembler.fromFinalizedResult(
                    lifecycleService.finalizePlanningFailure(handle, ex.failure()));
        } catch (PlanningCancellationException ex) {
            return responseAssembler.fromFinalizedResult(
                    lifecycleService.finalizeCancelled(handle, ex.cancellation()));
        }
    }

    private java.time.Instant absoluteDeadline() {
        return clock.instant().plus(properties.getRuntime().getReadTimeout());
    }
}
