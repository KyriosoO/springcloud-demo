package com.dylan.agent.application;

import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Instant;
import java.util.Objects;

/**
 * 入口层创建 CHAT 调用前的不可变命令。
 */
public record StartChatCommand(
        AgentUserContext userContext,
        String conversationId,
        String message,
        String requestedProfile,
        String materialType,
        AgentProfileRef agentProfileRef,
        Instant absoluteDeadline) {

    public StartChatCommand {
        Objects.requireNonNull(userContext, "userContext must not be null");
        conversationId = normalizeOptional(conversationId);
        message = requireText(message, "message");
        requestedProfile = normalizeOptional(requestedProfile);
        materialType = normalizeOptional(materialType);
        Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        Objects.requireNonNull(absoluteDeadline, "absoluteDeadline must not be null");
    }

    private static String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }

    private static String requireText(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
