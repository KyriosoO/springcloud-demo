package com.dylan.agent.metadata.authorization.internal;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.metadata.policy.model.SecurityClassificationRef;
import com.dylan.agent.model.MaskType;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class ExternalProcessingAuthorizationEvidenceFactoryTest {
    private static final String DOMAIN = "employee";
    private static final CapabilityOperationType PURPOSE =
            CapabilityOperationType.of("DOCUMENT_GENERATION");
    private static final CanonicalFieldRef NAME = new CanonicalFieldRef(DOMAIN, "name");
    private static final CanonicalFieldRef EMAIL = new CanonicalFieldRef(DOMAIN, "email");

    @Test
    void keepsPolicyDigestStableWhilePermissionIntersectionNarrows() {
        var factory = new ExternalProcessingAuthorizationEvidenceFactory();
        var policy = policy();
        var all = factory.create("policy-v1", permission(Set.of("name", "email")), Set.of(DOMAIN),
                fieldAccess(Set.of(NAME, EMAIL)), policy);
        var narrowed = factory.create("policy-v1", permission(Set.of("name")), Set.of(DOMAIN),
                fieldAccess(Set.of(NAME)), policy);

        assertThat(narrowed.policyEvidenceDigest()).isEqualTo(all.policyEvidenceDigest());
        assertThat(narrowed.fieldRules()).containsOnlyKeys(NAME);
        assertThat(narrowed.isSameOrNarrowerThan(all)).isTrue();
        assertThat(all.isSameOrNarrowerThan(narrowed)).isFalse();
    }

    private static Map<String, DomainSecurityConstraints> policy() {
        SecurityClassificationRef classification =
                new SecurityClassificationRef("test", "internal", "v1");
        return Map.of(DOMAIN, new DomainSecurityConstraints(Set.of(PURPOSE), Map.of(
                NAME, field(classification), EMAIL, field(classification))));
    }

    private static DomainSecurityConstraints.FieldSecurityConstraint field(
            SecurityClassificationRef classification) {
        return new DomainSecurityConstraints.FieldSecurityConstraint(
                true, true, Set.of(AgentOperator.EQ), Set.of(), Optional.of(MaskType.NONE),
                classification, Set.of(PURPOSE));
    }

    private static Map<CanonicalFieldRef, PlanningEffectiveScope.FieldAccess> fieldAccess(
            Set<CanonicalFieldRef> fields) {
        return fields.stream().collect(java.util.stream.Collectors.toUnmodifiableMap(
                field -> field,
                field -> new PlanningEffectiveScope.FieldAccess(
                        true, true, Set.of(AgentOperator.EQ), Set.of(), Optional.of(MaskType.NONE))));
    }

    private static UserPermission permission(Set<String> fields) {
        return new UserPermission(
                new ExecutionSubjectRef("user", "u-1"), "perm-evidence", "perm-v1",
                Set.of("document.answer"), Set.of(DOMAIN),
                Map.of(DOMAIN, fields), Map.of(DOMAIN, fields), Map.of(), Map.of(),
                Set.of("DOCUMENT"), Set.of("DOCUMENT"), Map.of(), Instant.parse("2026-07-14T00:00:00Z"));
    }
}
