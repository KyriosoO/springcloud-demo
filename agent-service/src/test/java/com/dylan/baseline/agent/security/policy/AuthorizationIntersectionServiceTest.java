package com.dylan.baseline.agent.security.policy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.baseline.agent.security.authorization.AuthAuthorizationFacts;
import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class AuthorizationIntersectionServiceTest {

    private final AuthorizationIntersectionService service = new AuthorizationIntersectionService();

    @Test
    void dualReadUsesIntersectionAndAgentAuthorityIgnoresLegacyExpansion() {
        LegacyAuthFieldView legacy = fields(Set.of("name", "phone"));
        LegacyAuthFieldView agent = fields(Set.of("name", "email"));
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", agent));

        assertThat(service.resolveFields(facts(), policy, legacy,
                AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION).filterableFields())
                .containsEntry("employee", Set.of("name"));
        assertThat(service.resolveFields(facts(), policy, legacy,
                AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY).filterableFields())
                .containsEntry("employee", Set.of("name", "email"));
    }

    @Test
    void seedModeCannotAuthorizeAndModeCannotRollBackToLegacyAuthority() {
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", fields(Set.of("name"))));

        assertThatThrownBy(() -> service.resolveFields(facts(), policy, fields(Set.of("name")),
                AuthFieldMigrationMode.SEED_ONLY))
                .isInstanceOf(IllegalStateException.class);
        assertThat(AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY
                .canTransitionTo(AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION)).isFalse();
        assertThat(AuthFieldMigrationMode.AUTH_FIELD_REMOVED
                .canTransitionTo(AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY)).isFalse();
    }

    private static AuthAuthorizationFacts facts() {
        return new AuthAuthorizationFacts(
                new SubjectRef("USER", "viewer_t"), "tenant-main", Set.of("agent-viewer"),
                Set.of("query.search"), Set.of("employee"), Set.of("QUERY"), Set.of("QUERY"),
                "evidence-1", "authz-v1",
                Instant.parse("2026-07-22T00:00:00Z"), Instant.parse("2026-07-22T00:01:00Z"));
    }

    private static LegacyAuthFieldView fields(Set<String> fields) {
        return new LegacyAuthFieldView(Map.of("employee", fields), Map.of("employee", fields), Map.of(), Map.of());
    }
}
