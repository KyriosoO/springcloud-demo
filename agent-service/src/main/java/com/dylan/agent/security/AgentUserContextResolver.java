package com.dylan.agent.security;

import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Component;

import com.dylan.agent.model.AgentUserContext;

/**
 * 从 JWT 解析 AgentUserContext。
 * 身份只来自认证上下文，不信任 X-USER-ID。
 */
@Component
public class AgentUserContextResolver {

    /** 从当前请求中解析 JWT 并提取用户 ID 和角色集合。 */
    public AgentUserContext resolve(Jwt jwt) {
        if (jwt == null) {
            throw new SecurityException("Missing JWT");
        }
        String userId = jwt.getSubject();
        if (userId == null || userId.isBlank()) {
            throw new SecurityException("Missing JWT subject");
        }
        Set<String> roles = extractRoles(jwt);
        return new AgentUserContext(userId, roles);
    }

    @SuppressWarnings("unchecked")
    private Set<String> extractRoles(Jwt jwt) {
        Object roleClaim = jwt.getClaims().get("role");
        if (roleClaim == null) {
            return Collections.emptySet();
        }
        Set<String> roles = new HashSet<>();
        if (roleClaim instanceof Collection<?> collection) {
            for (Object item : collection) {
                if (item instanceof String s && !s.isBlank()) {
                    roles.add(s.trim());
                }
            }
        } else if (roleClaim.getClass().isArray()) {
            for (Object item : (Object[]) roleClaim) {
                if (item instanceof String s && !s.isBlank()) {
                    roles.add(s.trim());
                }
            }
        } else if (roleClaim instanceof String s && !s.isBlank()) {
            roles.add(s.trim());
        }
        return Collections.unmodifiableSet(roles);
    }
}
