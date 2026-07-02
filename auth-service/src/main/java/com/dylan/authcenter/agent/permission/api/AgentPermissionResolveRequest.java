package com.dylan.authcenter.agent.permission.api;

import java.time.Instant;
import java.util.Set;

/**
 * agent-service 调用 auth-service 查询用户权限投影的内部请求。
 *
 * <p>requestedCapabilityIds/requestedDomains 只允许收敛输出范围，不是授权事实来源。</p>
 */
public record AgentPermissionResolveRequest(
        String requestId,
        SubjectRefDto subject,
        Instant requestedAt,
        Instant deadline,
        String agentId,
        String profileId,
        String scopeType,
        String scopeId,
        Set<String> requestedCapabilityIds,
        Set<String> requestedDomains) {
}
