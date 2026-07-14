package com.dylan.agent.model;

import java.util.Objects;

/**
 * 经过认证的用户上下文。
 * 身份只来自 Gateway 校验并透传的 JWT。
 */
public class AgentUserContext {

    private final String userId;

    public AgentUserContext(String userId) {
        this.userId = Objects.requireNonNull(userId, "userId must not be null");
        if (userId.isBlank()) {
            throw new IllegalArgumentException("userId must not be blank");
        }
    }

    public String getUserId() {
        return userId;
    }

}
