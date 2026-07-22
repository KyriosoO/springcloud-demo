package com.dylan.baseline.agent.security.authorization.internal;

import com.dylan.baseline.agent.security.authorization.AuthAuthorizationFacts;
import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import com.dylan.baseline.agent.security.authorization.ResolvedAuthPermission;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import java.time.Clock;
import java.time.Instant;

/** 严格校验Auth响应，并把旧字段隔离为仅迁移可见的视图。 */
public final class AuthPermissionAuthorityAdapter {

    private final Clock clock;

    public AuthPermissionAuthorityAdapter(Clock clock) {
        this.clock = clock;
    }

    public ResolvedAuthPermission map(
            AuthPermissionWireResponse response,
            SubjectRef expectedSubject,
            String expectedTenantRef,
            Instant absoluteDeadline) {
        if (response == null || expectedSubject == null || isBlank(expectedTenantRef) || absoluteDeadline == null) {
            throw new AuthPermissionValidationException("AUTH_RESPONSE_CONTEXT_INVALID");
        }
        Instant now = Instant.now(clock);
        if (!expectedSubject.equals(response.subject())) {
            throw new AuthPermissionValidationException("SECURITY_SUBJECT_MISMATCH");
        }
        if (!expectedTenantRef.equals(response.tenantRef())) {
            throw new AuthPermissionValidationException("SECURITY_TENANT_UNVERIFIED");
        }
        if (response.resolvedAt() == null || response.validUntil() == null
                || response.resolvedAt().isAfter(now)
                || !now.isBefore(response.validUntil())
                || !now.isBefore(absoluteDeadline)
                || response.validUntil().isAfter(absoluteDeadline)) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_STALE");
        }
        try {
            AuthAuthorizationFacts facts = new AuthAuthorizationFacts(
                    response.subject(), response.tenantRef(), response.permissionCodes(),
                    response.allowedCapabilityIds(), response.allowedDomains(),
                    response.readableContextTypes(), response.writableContextTypes(),
                    response.evidenceId(), response.version(), response.resolvedAt(), response.validUntil());
            LegacyAuthFieldView legacy = new LegacyAuthFieldView(
                    response.filterableFields(), response.displayableFields(),
                    response.allowedOperators(), response.allowedFunctions());
            return new ResolvedAuthPermission(facts, legacy);
        } catch (IllegalArgumentException ex) {
            throw new AuthPermissionValidationException("SECURITY_AUTH_FACT_UNAVAILABLE", ex);
        }
    }

    private static boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
