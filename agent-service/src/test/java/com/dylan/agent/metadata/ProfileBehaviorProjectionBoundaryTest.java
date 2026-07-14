package com.dylan.agent.metadata;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;

import org.junit.jupiter.api.Test;

import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.config.AgentMetadataStore;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.profile.internal.ProfileBehaviorProjectionBoundary;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;

class ProfileBehaviorProjectionBoundaryTest {
    @Test
    void projectsOnlyBehaviorInstructions() {
        var bundle = MetadataTestSupport.bundle("bundle-v1", "digest-v1");
        var profile = bundle.requireProfile(new AgentProfileVersionKey("agent-default", "profile-v1"));
        var evidence = com.dylan.agent.testsupport.PlanningAuthorizationEvidenceTestFactory.create(
                "corr", "user:u-1", profile.key(), bundle.bundleVersion(), bundle.bundleDigest(),
                "policy-v1", "perm", "perm-v1", DelegationConstraintRef.CHAT_ALL,
                new com.dylan.agent.metadata.profile.internal.EffectiveProfileCalculator().compute(profile, bundle.activePolicy()),
                com.dylan.agent.testsupport.PlanningEffectiveScopeTestFactory.create(
                        java.util.Set.of("query.search"), java.util.Set.of("employee"), java.util.Map.of(),
                        java.util.Set.of(), java.util.Set.of(),
                        com.dylan.agent.api.capability.AgentCapabilityRiskLevel.READ_ONLY,
                        com.dylan.agent.api.capability.AgentCapabilityExecutionMode.IMMEDIATE,
                        java.time.Duration.ofSeconds(30), 1, 100, 100, 10_000),
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog", "adapter", "availability", Instant.parse("2026-07-02T00:00:00Z")),
                Instant.parse("2026-07-02T00:00:00Z"),
                Instant.parse("2026-07-02T00:01:00Z"));

        var projection = new ProfileBehaviorProjectionBoundary(new AgentMetadataStore(bundle)).project(evidence);

        assertThat(projection.getInstructions()).containsExactly("只回答授权范围内的问题");
        assertThat(projection.getLocale()).isEqualTo("zh-CN");
    }
}
