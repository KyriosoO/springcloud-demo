package com.dylan.baseline.agent.security.authorization.internal;

import com.dylan.baseline.agent.security.authorization.SubjectRef;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

/** 当前兼容期Auth内部响应的transport模型。 */
public record AuthPermissionWireResponse(
        SubjectRef subject,
        String tenantRef,
        Set<String> permissionCodes,
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
        Instant resolvedAt,
        Instant validUntil) {
}
