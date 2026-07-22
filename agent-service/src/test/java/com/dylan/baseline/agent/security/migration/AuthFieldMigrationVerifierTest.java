package com.dylan.baseline.agent.security.migration;

import static org.assertj.core.api.Assertions.assertThat;

import com.dylan.baseline.agent.security.authorization.LegacyAuthFieldView;
import com.dylan.baseline.agent.security.authorization.AuthAuthorizationFacts;
import com.dylan.baseline.agent.security.authorization.SubjectRef;
import com.dylan.baseline.agent.security.policy.AgentFieldPolicySnapshot;
import com.dylan.baseline.agent.security.policy.AuthFieldMigrationMode;
import com.dylan.baseline.agent.security.policy.AuthorizationIntersectionService;
import java.io.IOException;
import java.io.InputStream;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

/** 对全部当前Auth profile执行可复算离线迁移差异。 */
class AuthFieldMigrationVerifierTest {

    private static final Map<String, String> APPROVED_PROFILE_BY_PERMISSION_CODE = Map.of(
            "agent-admin", "agent-admin",
            "agent-viewer", "agent-viewer");

    @Test
    void allKnownProfilesHaveApprovedEqualAgentSeeds() throws IOException {
        Map<String, LegacyAuthFieldView> authProfiles = loadAuthProfiles();
        assertApprovedRoleMappings();
        Map<String, LegacyAuthFieldView> agentSeeds = loadAgentSeeds();
        AuthFieldMigrationComparator comparator = new AuthFieldMigrationComparator();
        Map<String, AuthFieldMigrationDiffClass> result = new TreeMap<>();

        APPROVED_PROFILE_BY_PERMISSION_CODE.forEach((code, profileId) ->
                result.put(code, comparator.compare(authProfiles.get(profileId), agentSeeds.get(code))));

        assertThat(Set.copyOf(APPROVED_PROFILE_BY_PERMISSION_CODE.values()))
                .containsExactlyInAnyOrderElementsOf(authProfiles.keySet());
        assertThat(agentSeeds.keySet())
                .containsExactlyInAnyOrderElementsOf(APPROVED_PROFILE_BY_PERMISSION_CODE.keySet());
        assertThat(result).allSatisfy((code, diffClass) ->
                assertThat(diffClass).as(code).isEqualTo(AuthFieldMigrationDiffClass.EQUAL));
        assertThat(result.values()).doesNotContain(
                AuthFieldMigrationDiffClass.AGENT_WIDER_THAN_AUTH,
                AuthFieldMigrationDiffClass.UNMAPPABLE);
    }

    @Test
    void detectsWideningAndUnmappableSeed() {
        AuthFieldMigrationComparator comparator = new AuthFieldMigrationComparator();
        LegacyAuthFieldView auth = view(Map.of("employee", Set.of("name")));
        LegacyAuthFieldView wider = view(Map.of("employee", Set.of("name", "email")));
        LegacyAuthFieldView mixed = view(Map.of("transaction", Set.of("amount")));

        assertThat(comparator.compare(auth, wider))
                .isEqualTo(AuthFieldMigrationDiffClass.AGENT_WIDER_THAN_AUTH);
        assertThat(comparator.compare(auth, mixed))
                .isEqualTo(AuthFieldMigrationDiffClass.UNMAPPABLE);
    }

    @Test
    void controlledBAndCObservationExecutesActualResolverOneHundredTimesPerKnownProfile() throws IOException {
        Map<String, LegacyAuthFieldView> authProfiles = loadAuthProfiles();
        Map<String, LegacyAuthFieldView> agentSeeds = loadAgentSeeds();
        AuthorizationIntersectionService service = new AuthorizationIntersectionService();
        AgentFieldPolicySnapshot policy = new AgentFieldPolicySnapshot(
                "controlled-observation-v1", "d".repeat(64), agentSeeds);
        int phaseCLegacyDecisionReads = 0;

        for (Map.Entry<String, String> mapping : APPROVED_PROFILE_BY_PERMISSION_CODE.entrySet()) {
            AuthAuthorizationFacts facts = new AuthAuthorizationFacts(
                    new SubjectRef("USER", "controlled-observation"), "tenant-controlled",
                    Set.of(mapping.getKey()), Set.of(), Set.of(), Set.of(), Set.of(),
                    "evidence-" + mapping.getKey(), "v1",
                    Instant.parse("2026-07-22T00:00:00Z"), Instant.parse("2026-07-23T00:00:00Z"));
            LegacyAuthFieldView legacy = authProfiles.get(mapping.getValue());
            for (int iteration = 0; iteration < 100; iteration++) {
                AuthFieldMigrationResolution phaseB = service.resolveFieldsWithObservation(
                        facts, policy, legacy, AuthFieldMigrationMode.DUAL_READ_ENFORCE_INTERSECTION);
                AuthFieldMigrationResolution phaseC = service.resolveFieldsWithObservation(
                        facts, policy, legacy, AuthFieldMigrationMode.AGENT_FIELD_AUTHORITY);
                assertThat(phaseB.observedDiffClass()).contains(AuthFieldMigrationDiffClass.EQUAL);
                assertThat(phaseB.legacyUsedForDecision()).isTrue();
                assertThat(phaseC.observedDiffClass()).contains(AuthFieldMigrationDiffClass.EQUAL);
                assertThat(phaseC.legacyUsedForDecision()).isFalse();
                if (phaseC.legacyUsedForDecision()) {
                    phaseCLegacyDecisionReads++;
                }
            }
        }
        assertThat(phaseCLegacyDecisionReads).isZero();
    }

    private static Map<String, LegacyAuthFieldView> loadAgentSeeds() throws IOException {
        Map<String, Object> root = loadYaml("agent-security/migration/field-policy-seed-v0.1.yml");
        Map<String, Object> auth = map(loadAuthRoot().get("auth"), "auth");
        Map<String, Object> rbac = map(auth.get("rbac"), "auth.rbac");
        assertThat(root).containsEntry("activation-eligible", false);
        assertThat(root.get("source-auth-rule-version")).isEqualTo(rbac.get("rule-version"));
        Map<String, Object> policies = map(root.get("field-policies"), "field-policies");
        Map<String, LegacyAuthFieldView> result = new LinkedHashMap<>();
        policies.forEach((permissionCode, value) -> {
            Map<String, Object> policy = map(value, "field policy " + permissionCode);
            result.put(permissionCode,
                    new LegacyAuthFieldView(
                            fieldMap(policy.get("filterable-fields")),
                            fieldMap(policy.get("displayable-fields")),
                            fieldMap(policy.get("allowed-operators")),
                            fieldMap(policy.get("allowed-functions"))));
        });
        return result;
    }

    private static Map<String, LegacyAuthFieldView> loadAuthProfiles() throws IOException {
        Map<String, Object> root = loadAuthRoot();
        Map<String, Object> auth = map(root.get("auth"), "auth");
        Map<String, Object> rbac = map(auth.get("rbac"), "auth.rbac");
        Map<String, Object> profiles = map(rbac.get("permission-profiles"), "permission-profiles");
        Map<String, LegacyAuthFieldView> result = new LinkedHashMap<>();
        profiles.forEach((profileId, value) -> {
            Map<String, Object> profile = map(value, "permission profile " + profileId);
            result.put(profileId,
                new LegacyAuthFieldView(
                        fieldMap(profile.get("filterable-fields")),
                        fieldMap(profile.get("displayable-fields")),
                        fieldMap(profile.get("allowed-operators")),
                        fieldMap(profile.get("allowed-functions"))));
        });
        return result;
    }

    private static void assertApprovedRoleMappings() throws IOException {
        Map<String, Object> auth = map(loadAuthRoot().get("auth"), "auth");
        Map<String, Object> rbac = map(auth.get("rbac"), "auth.rbac");
        Map<String, Object> roles = map(rbac.get("roles"), "roles");
        java.util.Set<String> observedCodes = new java.util.TreeSet<>();
        roles.forEach((roleId, value) -> {
            Map<String, Object> role = map(value, "role " + roleId);
            String profileId = String.valueOf(role.get("permission-profile"));
            Object codesValue = role.get("permission-codes");
            if (!(codesValue instanceof List<?> codes) || codes.isEmpty()) {
                throw new IllegalStateException("role permission-codes must not be empty: " + roleId);
            }
            codes.stream().map(String::valueOf).forEach(code -> {
                observedCodes.add(code);
                assertThat(APPROVED_PROFILE_BY_PERMISSION_CODE)
                        .containsEntry(code, profileId);
            });
        });
        assertThat(observedCodes).containsExactlyInAnyOrderElementsOf(
                APPROVED_PROFILE_BY_PERMISSION_CODE.keySet());
    }

    private static Map<String, Object> loadAuthRoot() throws IOException {
        return loadYaml("agent-rbac.yml");
    }

    private static Map<String, Object> loadYaml(String resourcePath) throws IOException {
        try (InputStream input = AuthFieldMigrationVerifierTest.class
                .getClassLoader().getResourceAsStream(resourcePath)) {
            if (input == null) {
                throw new IOException(resourcePath + " is not available to migration verifier");
            }
            return new Yaml().load(input);
        }
    }

    private static LegacyAuthFieldView view(Map<String, Set<String>> fields) {
        return new LegacyAuthFieldView(fields, fields, Map.of(), Map.of());
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> map(Object value, String name) {
        if (!(value instanceof Map<?, ?> map)) {
            throw new IllegalStateException(name + " must be an object");
        }
        return (Map<String, Object>) map;
    }

    private static Map<String, Set<String>> fieldMap(Object value) {
        if (value == null) {
            return Map.of();
        }
        Map<String, Object> raw = map(value, "field map");
        Map<String, Set<String>> result = new LinkedHashMap<>();
        raw.forEach((key, entries) -> {
            if (!(entries instanceof List<?> list)) {
                throw new IllegalStateException("field map value must be a list: " + key);
            }
            result.put(key, list.stream().map(String::valueOf).collect(java.util.stream.Collectors.toSet()));
        });
        return result;
    }
}
