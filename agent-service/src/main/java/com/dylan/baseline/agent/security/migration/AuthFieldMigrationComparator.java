package com.dylan.baseline.agent.security.migration;

import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;

public final class AuthFieldMigrationComparator {

    public AuthFieldMigrationDiffClass compare(
            LegacyAuthFieldView legacyAuth,
            LegacyAuthFieldView agentPolicy) {
        if (legacyAuth == null || agentPolicy == null) {
            return AuthFieldMigrationDiffClass.UNMAPPABLE;
        }
        boolean agentWithinAuth = agentPolicy.isSubsetOf(legacyAuth);
        boolean authWithinAgent = legacyAuth.isSubsetOf(agentPolicy);
        if (agentWithinAuth && authWithinAgent) {
            return AuthFieldMigrationDiffClass.EQUAL;
        }
        if (agentWithinAuth) {
            return AuthFieldMigrationDiffClass.AUTH_WIDER_THAN_AGENT;
        }
        if (authWithinAgent) {
            return AuthFieldMigrationDiffClass.AGENT_WIDER_THAN_AUTH;
        }
        return AuthFieldMigrationDiffClass.UNMAPPABLE;
    }
}
