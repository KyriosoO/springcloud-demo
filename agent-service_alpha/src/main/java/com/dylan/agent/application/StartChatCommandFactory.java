package com.dylan.agent.application;

import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Instant;
import java.util.Objects;

import org.springframework.stereotype.Component;

/**
 * 基于已认证入口输入构造 D03 CHAT 启动命令。
 */
@Component
public class StartChatCommandFactory {

    private static final int MAX_MESSAGE_CHARS = 2000;

    private final AgentProperties properties;

    public StartChatCommandFactory(AgentProperties properties) {
        this.properties = Objects.requireNonNull(properties);
    }

    public StartChatCommand create(
            AgentUserContext userContext,
            AgentChatRequest request,
            Instant absoluteDeadline) {
        Objects.requireNonNull(request, "request must not be null");
        return new StartChatCommand(
                userContext,
                request.getConversationId(),
                normalizeMessage(request.getMessage()),
                request.getRequestedProfile(),
                request.getMaterialType(),
                AgentProfileRef.of(
                        properties.getProfile().getAgentId(),
                        properties.getProfile().getProfileVersion()),
                absoluteDeadline);
    }

    private static String normalizeMessage(String message) {
        String normalized = message == null ? "" : message.trim();
        if (normalized.length() > MAX_MESSAGE_CHARS) {
            normalized = normalized.substring(0, MAX_MESSAGE_CHARS);
        }
        return normalized;
    }
}
