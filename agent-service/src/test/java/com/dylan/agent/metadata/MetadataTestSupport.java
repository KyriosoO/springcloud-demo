package com.dylan.agent.metadata;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.config.AgentMetadataBundle;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.policy.model.AgentPolicySnapshot;
import com.dylan.agent.metadata.policy.model.BudgetLimits;
import com.dylan.agent.metadata.policy.model.CapabilityConstraints;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.metadata.policy.model.ProfileConstraints;
import com.dylan.agent.metadata.profile.model.AgentProfileDefinition;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.ProfileBehaviorAsset;
import com.dylan.agent.metadata.profile.model.ProfileBehaviorAssetRef;

import java.time.Duration;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public final class MetadataTestSupport {

    public static final Instant NOW = Instant.parse("2026-07-02T00:00:00Z");

    private MetadataTestSupport() {
    }

    public static AgentMetadataBundle bundle(String version, String digest) {
        AgentProfileVersionKey profileKey = new AgentProfileVersionKey("agent-default", "profile-v1");
        ProfileBehaviorAssetRef assetRef = new ProfileBehaviorAssetRef("asset-default", "asset-v1");
        AgentProfileDefinition profile = new AgentProfileDefinition(
                profileKey,
                assetRef,
                Set.of("query.search"),
                Set.of(RuntimeContextType.QUERY),
                Set.of(RuntimeContextType.QUERY),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                100,
                100,
                10_000);
        ProfileBehaviorAsset asset = new ProfileBehaviorAsset(
                assetRef,
                java.util.List.of("只回答授权范围内的问题"),
                Optional.of(Locale.SIMPLIFIED_CHINESE));
        AgentPolicySnapshot policy = policy();
        return new AgentMetadataBundle(
                version,
                digest,
                "agent-default",
                Map.of("agent-default", "profile-v1"),
                policy.policyVersion(),
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ofMinutes(5), 10, "ACTIVE"),
                Map.of(profileKey, profile),
                Map.of(assetRef, asset),
                Map.of(policy.policyVersion(), policy));
    }

    public static AgentPolicySnapshot policy() {
        return new AgentPolicySnapshot(
                "policy-v1",
                Map.of("agent-default", new ProfileConstraints(
                        true,
                        Set.of("query.search"),
                        Set.of(RuntimeContextType.QUERY),
                        Set.of(RuntimeContextType.QUERY),
                        Optional.of(AgentCapabilityRiskLevel.READ_ONLY),
                        Optional.of(AgentCapabilityExecutionMode.IMMEDIATE),
                        Optional.of(new BudgetLimits(Duration.ofSeconds(30), 1, 100, 100, 10_000)),
                        Optional.empty())),
                Map.of("query.search", new CapabilityConstraints(true, Optional.empty())),
                Map.of("employee", new DomainSecurityConstraints(Map.of())),
                new BudgetLimits(Duration.ofSeconds(30), 1, 100, 100, 10_000),
                Duration.ofHours(1),
                Set.of());
    }

    public static UserPermission permission(ExecutionSubjectRef subject) {
        return new UserPermission(
                subject,
                "perm-evidence",
                "perm-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of("employee", Set.of("chineseName")),
                Map.of("employee", Set.of("chineseName")),
                Map.of("employee.chineseName", Set.of(com.dylan.agent.api.enums.AgentOperator.EQ)),
                Map.of(),
                Set.of("QUERY"),
                Set.of("QUERY"),
                Map.of(),
                NOW);
    }
}
