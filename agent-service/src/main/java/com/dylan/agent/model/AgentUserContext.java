package com.dylan.agent.model;

import java.util.Set;

/**
 * 经过认证和角色解析的用户上下文。
 * 身份只来自 Gateway 校验并透传的 JWT。
 */
public class AgentUserContext {

    private final String userId;
    private final Set<String> roles;

    public AgentUserContext(String userId, Set<String> roles) {
        this.userId = userId;
        this.roles = Set.copyOf(roles);
    }

    public String getUserId() {
        return userId;
    }

    public Set<String> getRoles() {
        return roles;
    }

    public boolean hasRole(String role) {
        return roles.contains(role);
    }
}
