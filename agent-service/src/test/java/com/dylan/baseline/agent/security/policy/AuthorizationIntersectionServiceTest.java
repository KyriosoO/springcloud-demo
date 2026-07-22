package com.dylan.baseline.agent.security.policy;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.baseline.agent.security.authorization.AuthAuthorizationFacts;
import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import com.dylan.baseline.agent.security.migration.AuthFieldMigrationDiffClass;
import com.dylan.baseline.agent.security.migration.AuthFieldMigrationException;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

class AuthorizationIntersectionServiceTest {

    private final AuthorizationIntersectionService service = new AuthorizationIntersectionService();

    @Test
    void dualReadUsesIntersectionAndAgentAuthorityIgnoresLegacyNarrowing() {
        LegacyAuthFieldView legacy = fields(Set.of("name"));
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
        assertThat(AuthFieldMigrationMode.SEED_ONLY
                .canTransitionTo(AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY)).isFalse();
        assertThat(AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION
                .canTransitionTo(AuthFieldMigrationMode.AUTH_FIELD_REMOVED)).isFalse();
        assertThat(AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY
                .canTransitionTo(AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY)).isTrue();
    }

    @Test
    void agentAuthorityAndRemovedModesDoNotRequireOrReadLegacyFields() {
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", fields(Set.of("name", "email"))));

        assertThat(service.resolveFields(facts(), policy, null,
                AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY).filterableFields())
                .containsEntry("employee", Set.of("name", "email"));
        assertThat(service.resolveFields(facts(), policy, null,
                AuthFieldMigrationMode.AUTH_FIELD_REMOVED).filterableFields())
                .containsEntry("employee", Set.of("name", "email"));
        assertThat(service.resolveFields(facts(), policy, fields(Set.of("phone")),
                AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY).filterableFields())
                .containsEntry("employee", Set.of("name", "email"));
    }

    @Test
    void dualReadStillRequiresLegacyViewAndCannotWidenAgentPolicy() {
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", fields(Set.of("name", "email"))));

        assertThatThrownBy(() -> service.resolveFields(
                facts(), policy, null, AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("required only in dual-read mode");
        assertThat(service.resolveFields(facts(), policy, fields(Set.of("name")),
                AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION).filterableFields())
                .containsEntry("employee", Set.of("name"));
    }

    @Test
    void dualReadExposesLowCardinalityDiffAndFailsClosedWhenUnmappable() {
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", fields(Set.of("name", "email"))));

        var resolution = service.resolveFieldsWithObservation(
                facts(), policy, fields(Set.of("name")),
                AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION);
        assertThat(resolution.observedDiffClass())
                .contains(AuthFieldMigrationDiffClass.AGENT_WIDER_THAN_AUTH);
        assertThat(resolution.legacyUsedForDecision()).isTrue();
        assertThatThrownBy(() -> service.resolveFieldsWithObservation(
                facts(), policy, new LegacyAuthFieldView(
                        Map.of("transaction", Set.of("amount")),
                        Map.of("transaction", Set.of("amount")), Map.of(), Map.of()),
                AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION))
                .isInstanceOfSatisfying(AuthFieldMigrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_AUTH_FIELD_MIGRATION_UNMAPPABLE"));
    }

    @Test
    void agentAuthorityObservesLegacyWithoutUsingItAndRemovedModeDoesNotObserveIt() {
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", fields(Set.of("name"))));

        var authority = service.resolveFieldsWithObservation(
                facts(), policy, fields(Set.of("name", "phone")),
                AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY);
        assertThat(authority.observedDiffClass())
                .contains(AuthFieldMigrationDiffClass.AUTH_WIDER_THAN_AGENT);
        assertThat(authority.legacyUsedForDecision()).isFalse();

        var removed = service.resolveFieldsWithObservation(
                facts(), policy, fields(Set.of("phone")), AuthFieldMigrationMode.AUTH_FIELD_REMOVED);
        assertThat(removed.observedDiffClass()).isEmpty();
        assertThat(removed.legacyUsedForDecision()).isFalse();
    }

    @Test
    void unknownPermissionCodeIsUnmappableAndNeverSilentlyIgnored() {
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "policy-v1", "a".repeat(64), Map.of("agent-viewer", fields(Set.of("name"))));
        AuthAuthorizationFacts unknownCodeFacts = new AuthAuthorizationFacts(
                new SubjectRef("USER", "viewer_t"), "tenant-main", Set.of("agent-viewer", "unknown-code"),
                Set.of("query.search"), Set.of("employee"), Set.of("QUERY"), Set.of("QUERY"),
                "evidence-1", "authz-v1",
                Instant.parse("2026-07-22T00:00:00Z"), Instant.parse("2026-07-22T00:01:00Z"));

        assertThatThrownBy(() -> service.resolveFieldsWithObservation(
                unknownCodeFacts, policy, null, AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY))
                .isInstanceOfSatisfying(AuthFieldMigrationException.class,
                        ex -> {
                            assertThat(ex.code()).isEqualTo("SECURITY_AUTH_FIELD_MIGRATION_UNMAPPABLE");
                            assertThat(ex.getMessage()).doesNotContain("unknown-code");
                        });
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
