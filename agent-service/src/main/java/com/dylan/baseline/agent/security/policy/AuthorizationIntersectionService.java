package com.dylan.baseline.agent.security.policy;

import com.dylan.baseline.agent.security.authorization.AuthAuthorizationFacts;
import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import com.dylan.baseline.agent.security.migration.AuthFieldMigrationComparator;
import com.dylan.baseline.agent.security.migration.AuthFieldMigrationDiffClass;
import com.dylan.baseline.agent.security.migration.AuthFieldMigrationException;
import com.dylan.baseline.agent.security.migration.AuthFieldMigrationResolution;
import java.util.Optional;

/** 只收紧组合Agent字段策略与迁移期Auth旧字段视图。 */
public final class AuthorizationIntersectionService {

    private final AuthFieldMigrationComparator migrationComparator;

    public AuthorizationIntersectionService() {
        this(new AuthFieldMigrationComparator());
    }

    AuthorizationIntersectionService(AuthFieldMigrationComparator migrationComparator) {
        this.migrationComparator = java.util.Objects.requireNonNull(migrationComparator, "migrationComparator");
    }

    public LegacyAuthFieldView resolveFields(
            AuthAuthorizationFacts authFacts,
            AgentFieldPolicySnapshot policy,
            LegacyAuthFieldView legacyView,
            AuthFieldMigrationMode migrationMode) {
        return resolveFieldsWithObservation(authFacts, policy, legacyView, migrationMode).effectiveFields();
    }

    public AuthFieldMigrationResolution resolveFieldsWithObservation(
            AuthAuthorizationFacts authFacts,
            AgentFieldPolicySnapshot policy,
            LegacyAuthFieldView legacyView,
            AuthFieldMigrationMode migrationMode) {
        if (authFacts == null || policy == null || migrationMode == null) {
            throw new IllegalArgumentException("authorization facts, policy and migration mode must not be null");
        }
        if (migrationMode == AuthFieldMigrationMode.SEED_ONLY) {
            throw new IllegalStateException("SEED_ONLY does not authorize runtime field access");
        }
        boolean missingPermissionCodeMapping = authFacts.permissionCodes().stream()
                .anyMatch(code -> !policy.fieldPolicyByPermissionCode().containsKey(code));
        if (missingPermissionCodeMapping) {
            throw new AuthFieldMigrationException(
                    "SECURITY_AUTH_FIELD_MIGRATION_UNMAPPABLE",
                    "one or more Auth permission codes have no Agent field policy mapping");
        }
        LegacyAuthFieldView agentFields = authFacts.permissionCodes().stream()
                .map(policy.fieldPolicyByPermissionCode()::get)
                .reduce(LegacyAuthFieldView.empty(), LegacyAuthFieldView::union);
        if (migrationMode == AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION) {
            if (legacyView == null) {
                throw new IllegalArgumentException("legacy field view is required only in dual-read mode");
            }
            AuthFieldMigrationDiffClass diffClass = migrationComparator.compare(legacyView, agentFields);
            if (diffClass == AuthFieldMigrationDiffClass.UNMAPPABLE) {
                throw new AuthFieldMigrationException(
                        "SECURITY_AUTH_FIELD_MIGRATION_UNMAPPABLE",
                        "legacy Auth fields cannot be mapped to the active Agent policy");
            }
            return new AuthFieldMigrationResolution(
                    agentFields.intersect(legacyView), Optional.of(diffClass), true);
        }
        if (migrationMode == AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY && legacyView != null) {
            return new AuthFieldMigrationResolution(
                    agentFields, Optional.of(migrationComparator.compare(legacyView, agentFields)), false);
        }
        return new AuthFieldMigrationResolution(agentFields, Optional.empty(), false);
    }
}
