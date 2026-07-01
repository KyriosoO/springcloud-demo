package com.dylan.agent.application;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.capability.CapabilityRouteResolver;
import com.dylan.agent.capability.CapabilityRouter;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.CapabilityDescriptorFactory;
import com.dylan.agent.capability.model.ValidatedCapabilityPlan;
import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.conversation.ConversationHandle;
import com.dylan.agent.conversation.ConversationService;
import com.dylan.agent.conversation.TurnHandle;
import com.dylan.agent.exception.AgentException;
import com.dylan.agent.exception.AgentInternalException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.planning.RuntimeDomainSchemaProjection;
import com.dylan.agent.security.AgentPermissionService;

/**
 * Agent 聊天主流程编排器。仅负责生命周期：打开会话、创建 turn、调用 Runtime
 * 生成 plan、通过 {@link CapabilityRouteResolver} 解析 intent、路由到正确的
 * {@link AgentCapabilityHandler}、完成 turn、构建响应。
 *
 * <p>不包含任何具体 intent 的执行逻辑，全部下沉到 capability handler。
 * {@link #validateUnchecked} / {@link #executeUnchecked} 是原始类型桥接方法，
 * {@code @SuppressWarnings("unchecked")} 安全是因为类型擦除仅发生在
 * orchestrator 私有方法内。
 */
@Component
public class AgentOrchestrator {

    private static final Logger log = LoggerFactory.getLogger(AgentOrchestrator.class);

    private final ConversationService conversationService;
    private final RuntimeDomainSchemaProjection schemaProjection;
    private final AgentRuntimeClient runtimeClient;
    private final AgentPermissionService permissionService;
    private final AgentProperties properties;
    private final CapabilityRouteResolver routeResolver;
    private final CapabilityRouter capabilityRouter;
    private final CapabilityDescriptorFactory capabilityDescriptorFactory;

    public AgentOrchestrator(ConversationService conversationService,
                             RuntimeDomainSchemaProjection schemaProjection,
                             AgentRuntimeClient runtimeClient,
                             AgentPermissionService permissionService,
                             AgentProperties properties,
                             CapabilityRouteResolver routeResolver,
                             CapabilityRouter capabilityRouter,
                             CapabilityDescriptorFactory capabilityDescriptorFactory) {
        this.conversationService = conversationService;
        this.schemaProjection = schemaProjection;
        this.runtimeClient = runtimeClient;
        this.permissionService = permissionService;
        this.properties = properties;
        this.routeResolver = routeResolver;
        this.capabilityRouter = capabilityRouter;
        this.capabilityDescriptorFactory = capabilityDescriptorFactory;
    }

    /** Agent 聊天主入口：打开会话 → 创建 turn → 调用 Runtime 生成 plan → 路由到 handler → 执行 → 完成 turn → 构建响应。 */
    public AgentChatResponse chat(AgentUserContext userContext, AgentChatRequest request) {
        permissionService.requireAgentAccess(userContext);

        String normalized = normalizeMessage(request.getMessage());

        ConversationHandle conv = conversationService.openConversation(
                request.getConversationId(), userContext.getUserId());

        TurnHandle turn = conversationService.startTurn(conv.conversationId(),
                userContext.getUserId(), normalized);

        try {
            var recentTurns = conversationService.loadRecentTurns(conv.conversationId(),
                    userContext.getUserId(), properties.getConversation().getRecentTurnLimit());
            RuntimeQueryContext previousQuery = conversationService.loadLatestQueryContext(
                    conv.conversationId(), userContext.getUserId());

            PlanGenerateRequest pgReq = new PlanGenerateRequest();
            pgReq.setRequestId(turn.turnId());
            pgReq.setMessage(normalized);
            pgReq.setRecentTurns(recentTurns);
            pgReq.setPreviousQuery(previousQuery);
            pgReq.setDomainSchemas(schemaProjection.createAll());
            pgReq.setCapabilities(capabilityDescriptorFactory.createForRuntimeRequest(userContext));

            PlanGenerateResponse pgResp = runtimeClient.generate(pgReq);

            AgentIntent intent = routeResolver.resolve(pgResp, turn.turnId());

            permissionService.checkIntent(userContext, intent);

            AgentCapabilityHandler<?> handler = capabilityRouter.route(intent);

            CapabilityValidationContext validationContext =
                    new CapabilityValidationContext(
                            pgResp,
                            turn.turnId(),
                            previousQuery,
                            userContext);

            ValidatedCapabilityPlan plan =
                    validateUnchecked(handler, validationContext);

            CapabilityExecutionContext executionContext =
                    new CapabilityExecutionContext(
                            conv.conversationId(),
                            turn.turnId(),
                            normalized,
                            userContext,
                            previousQuery);

            CapabilityExecutionResult result =
                    executeUnchecked(handler, executionContext, plan);

            completeTurn(turn.turnId(), result);

            return buildResponse(conv.conversationId(), turn.turnId(), result);

        } catch (AgentException e) {
            try {
                conversationService.completeFailure(turn.turnId(), e.getErrorCode(), e.getSafeMessage());
            } catch (Exception persistEx) {
                log.error("completeFailure 自身失败: turnId={}", turn.turnId(), persistEx);
            }
            throw e.withContext(conv.conversationId(), turn.turnId());
        } catch (Exception e) {
            try {
                conversationService.completeFailure(turn.turnId(), AgentErrorCode.AGENT_INTERNAL_ERROR,
                        "系统内部错误，请稍后重试。");
            } catch (Exception persistEx) {
                log.error("completeFailure 自身失败: turnId={}", turn.turnId(), persistEx);
            }
            throw new AgentInternalException("系统内部错误，请稍后重试。", e)
                    .withContext(conv.conversationId(), turn.turnId());
        }
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private ValidatedCapabilityPlan validateUnchecked(
            AgentCapabilityHandler handler,
            CapabilityValidationContext context) {
        return (ValidatedCapabilityPlan) handler.validate(context);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private CapabilityExecutionResult executeUnchecked(
            AgentCapabilityHandler handler,
            CapabilityExecutionContext context,
            ValidatedCapabilityPlan plan) {
        return handler.execute(context, plan);
    }

    private void completeTurn(String turnId, CapabilityExecutionResult result) {
        conversationService.completeSuccess(
                turnId,
                result.intent(),
                result.responseType(),
                result.assistantMessage(),
                result.contextToPersist());
    }

    private AgentChatResponse buildResponse(
            String conversationId,
            String turnId,
            CapabilityExecutionResult result) {
        AgentChatResponse resp = new AgentChatResponse();
        resp.setConversationId(conversationId);
        resp.setTurnId(turnId);
        result.applyTo(resp);
        return resp;
    }

    /** 截断消息至 2000 字符，匹配 Runtime 的最大长度约束。 */
    private String normalizeMessage(String message) {
        if (message == null) return "";
        String trimmed = message.trim();
        if (trimmed.length() > 2000) {
            trimmed = trimmed.substring(0, 2000);
        }
        return trimmed;
    }
}
