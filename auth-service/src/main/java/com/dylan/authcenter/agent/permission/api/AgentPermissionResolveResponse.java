package com.dylan.authcenter.agent.permission.api;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

/**
 * auth-service 返回给 agent-service 的完整权限投影。
 *
 * <p>响应字段必须覆盖 agent-service UserPermission；agent-service 不再根据 JWT role 推导权限。</p>
 */
public record AgentPermissionResolveResponse(
        SubjectRefDto subject,
        String evidenceId,
        String version,
        Set<String> allowedCapabilityIds,
        Set<String> allowedDomains,
        Map<String, Set<String>> filterableFields,
        Map<String, Set<String>> displayableFields,
        Map<String, Set<String>> allowedOperators,
        Map<String, Set<String>> allowedFunctions,
        Set<String> readableContextTypes,
        Set<String> writableContextTypes,
        Map<String, String> attributes,
        Instant resolvedAt) {
}
