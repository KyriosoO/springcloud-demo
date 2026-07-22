package com.dylan.baseline.agent.security.policy;

import com.dylan.baseline.agent.security.authorization.AuthAuthorizationFacts;
import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;

/** 只收紧组合Agent字段策略与迁移期Auth旧字段视图。 */
public final class AuthorizationIntersectionService {

    public LegacyAuthFieldView resolveFields(
            AuthAuthorizationFacts authFacts,
            AgentFieldPolicySnapshot policy,
            LegacyAuthFieldView legacyView,
            AuthFieldMigrationMode migrationMode) {
        if (authFacts == null || policy == null || legacyView == null || migrationMode == null) {
            throw new IllegalArgumentException("authorization inputs must not be null");
        }
        if (migrationMode == AuthFieldMigrationMode.SEED_ONLY) {
            throw new IllegalStateException("SEED_ONLY does not authorize runtime field access");
        }
        LegacyAuthFieldView agentFields = authFacts.permissionCodes().stream()
                .map(policy.fieldPolicyByPermissionCode()::get)
                .filter(java.util.Objects::nonNull)
                .reduce(LegacyAuthFieldView.empty(), LegacyAuthFieldView::union);
        if (migrationMode == AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION) {
            return agentFields.intersect(legacyView);
        }
        return agentFields;
    }
}
