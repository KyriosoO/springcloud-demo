package com.dylan.agent.security;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

import com.dylan.agent.model.AgentUserContext;

/**
 * 从 JWT 解析 AgentUserContext。
 * 身份只来自认证上下文，不信任 X-USER-ID。
 */
@Component
public class AgentUserContextResolver {

    /** 从当前请求中解析 JWT 并提取用户 ID。 */
    public AgentUserContext resolve(Jwt jwt) {
        if (jwt == null) {
            throw new SecurityException("Missing JWT");
        }
        String userId = jwt.getSubject();
        if (userId == null || userId.isBlank()) {
            throw new SecurityException("Missing JWT subject");
        }
        return new AgentUserContext(userId);
    }
}
