package com.dylan.agent.application;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentResponseType;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.lifecycle.model.FinalizedInvocationResult;
import com.dylan.agent.lifecycle.model.InvocationResponseType;

import java.util.Objects;

import org.springframework.stereotype.Component;

/**
 * 将已终结的调用状态映射为对外 Agent Chat 响应 DTO。
 */
@Component
public class AgentChatResponseAssembler {

    public AgentChatResponse fromFinalizedResult(FinalizedInvocationResult finalized) {
        Objects.requireNonNull(finalized, "finalized must not be null");
        if (!(finalized.origin() instanceof ChatInvocationOrigin chat)) {
            throw new IllegalArgumentException("AgentChatResponse requires CHAT origin");
        }
        AgentChatResponse response = new AgentChatResponse();
        response.setConversationId(chat.conversationId());
        response.setTurnId(chat.turnId());
        response.setMessage(finalized.safeMessage());
        response.setSummary(finalized.storedResult()
                .map(result -> result.safeSummary())
                .orElse(finalized.safeMessage()));
        response.setType(toAgentResponseType(finalized.responseType()));
        response.setErrorCode(finalized.errorCode()
                .map(AgentChatResponseAssembler::toAgentErrorCode)
                .orElse(null));
        response.setResult(finalized.storedResult()
                .flatMap(result -> result.payload())
                .orElse(null));
        return response;
    }

    private static AgentResponseType toAgentResponseType(InvocationResponseType responseType) {
        return switch (responseType) {
            case SUCCESS -> AgentResponseType.RESULT;
            case CLARIFY -> AgentResponseType.CLARIFY;
            case FAILURE, CANCELLED -> AgentResponseType.ERROR;
        };
    }

    private static AgentErrorCode toAgentErrorCode(KernelErrorCode code) {
        return switch (code) {
            case PROFILE_INVALID, POLICY_INVALID, CATALOG_INCONSISTENT,
                    REGISTRATION_MISMATCH, INTERNAL_ERROR ->
                    AgentErrorCode.AGENT_INTERNAL_ERROR;
            case PERMISSION_UNAVAILABLE, AUTH_EVIDENCE_CHANGED, AUTHORIZATION_REVOKED, FIELD_FORBIDDEN ->
                    AgentErrorCode.AGENT_FIELD_FORBIDDEN;
            case RUNTIME_CONTRACT_INVALID, RUNTIME_OUTPUT_INVALID ->
                    AgentErrorCode.AGENT_PLAN_INVALID;
            case RUNTIME_AUTHENTICATION_FAILED, RUNTIME_UNAVAILABLE, DEADLINE_EXCEEDED, CANCELLED ->
                    AgentErrorCode.AGENT_RUNTIME_UNAVAILABLE;
            case CONTEXT_REQUIRED_MISSING, CONTEXT_DECRYPT_FAILED, CONTEXT_STALE,
                    CONTEXT_WRITE_CONFLICT ->
                    AgentErrorCode.AGENT_INTERNAL_ERROR;
            case DOMAIN_BINDING_UNAVAILABLE, PLAN_VALIDATION_FAILED, OUTPUT_INVALID,
                    RESULT_SECURITY_FAILED ->
                    AgentErrorCode.AGENT_PLAN_INVALID;
            case HANDLER_FAILED, DOWNSTREAM_FAILED ->
                    AgentErrorCode.AGENT_QUERY_FAILED;
            case PERSISTENCE_FAILED ->
                    AgentErrorCode.AGENT_INTERNAL_ERROR;
        };
    }
}
