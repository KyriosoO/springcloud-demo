package com.dylan.baseline.agent.security.authorization;

import java.time.Instant;
import java.util.Set;
import java.util.TreeSet;

/** Auth 权威的 RBAC 上界；字段规则不属于该模型。 */
public record AuthAuthorizationFacts(
        SubjectRef subject,
        String tenantRef,
        Set<String> permissionCodes,
        Set<String> allowedCapabilityIds,
        Set<String> allowedDomains,
        Set<String> readableContextTypes,
        Set<String> writableContextTypes,
        String evidenceId,
        String version,
        Instant resolvedAt,
        Instant validUntil) {

    public AuthAuthorizationFacts {
        if (subject == null) {
            throw new IllegalArgumentException("subject must not be null");
        }
        requireText(tenantRef, "tenantRef");
        requireText(evidenceId, "evidenceId");
        requireText(version, "version");
        permissionCodes = immutableSet(permissionCodes, "permissionCodes");
        allowedCapabilityIds = immutableSet(allowedCapabilityIds, "allowedCapabilityIds");
        allowedDomains = immutableSet(allowedDomains, "allowedDomains");
        readableContextTypes = immutableSet(readableContextTypes, "readableContextTypes");
        writableContextTypes = immutableSet(writableContextTypes, "writableContextTypes");
        if (resolvedAt == null || validUntil == null || !validUntil.isAfter(resolvedAt)) {
            throw new IllegalArgumentException("invalid Auth fact validity window");
        }
    }

    private static Set<String> immutableSet(Set<String> values, String name) {
        if (values == null || values.stream().anyMatch(value -> value == null || value.isBlank())) {
            throw new IllegalArgumentException(name + " must be a non-null set of non-blank values");
        }
        return Set.copyOf(new TreeSet<>(values));
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
    }
}
