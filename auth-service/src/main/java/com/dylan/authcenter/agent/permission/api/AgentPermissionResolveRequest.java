package com.dylan.authcenter.agent.permission.api;

import java.time.Instant;

/** agent-service 调用 auth-service 查询当前用户权限投影的最小内部请求。 */
public record AgentPermissionResolveRequest(
        String requestId,
        SubjectRefDto subject,
        Instant requestedAt,
        Instant deadline) {
}
