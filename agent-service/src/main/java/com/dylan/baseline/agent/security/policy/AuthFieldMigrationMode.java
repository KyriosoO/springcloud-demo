package com.dylan.baseline.agent.security.policy;

public enum AuthFieldMigrationMode {
    SEED_ONLY,
    DUAL_READ_ENFORCE_INTERSECTION,
    AGENT_FIELD_AUTHORITY,
    AUTH_FIELD_REMOVED;

    public boolean canTransitionTo(AuthFieldMigrationMode target) {
        return target != null && target.ordinal() >= ordinal() && target.ordinal() - ordinal() <= 1;
    }
}
