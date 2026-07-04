package com.dylan.agent.metadata;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.config.AgentMetadataBundle;
import com.dylan.agent.metadata.config.AgentSecuritySettings;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
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
        return bundle(version, digest, Set.of("query.search"), Set.of("employee"), Set.of(RuntimeContextType.QUERY));
    }

    public static AgentMetadataBundle bundleWithActivePayloadKeyId(String version, String digest, String keyId) {
        return bundle(
                version,
                digest,
                Set.of("query.search"),
                Set.of("employee"),
                Set.of(RuntimeContextType.QUERY),
                keyId);
    }

    public static AgentMetadataBundle bundleWithQueryPreview(String version, String digest) {
        return bundle(
                version,
                digest,
                Set.of("query.search", "query.preview", "aggregate.compute"),
                Set.of("employee", "transaction"),
                Set.of(RuntimeContextType.QUERY, RuntimeContextType.AGGREGATE));
    }

    public static AgentMetadataBundle bundleWithEmployeeFieldSecurity(
            String version,
            String digest,
            Map<CanonicalFieldRef, DomainSecurityConstraints.FieldSecurityConstraint> fields) {
        return bundle(
                version,
                digest,
                Set.of("query.search"),
                Set.of("employee"),
                Set.of(RuntimeContextType.QUERY),
                Map.of("employee", new DomainSecurityConstraints(fields)));
    }

    private static AgentMetadataBundle bundle(
            String version,
            String digest,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Set<RuntimeContextType> contextTypes) {
        return bundle(version, digest, allowedCapabilityIds, allowedDomains, contextTypes, "ACTIVE");
    }

    private static AgentMetadataBundle bundle(
            String version,
            String digest,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Set<RuntimeContextType> contextTypes,
            String activePayloadKeyId) {
        return bundle(
                version,
                digest,
                allowedCapabilityIds,
                allowedDomains,
                contextTypes,
                allowedDomains.stream()
                        .collect(java.util.stream.Collectors.toUnmodifiableMap(
                                domain -> domain,
                                domain -> new DomainSecurityConstraints(Map.of()))),
                activePayloadKeyId);
    }

    private static AgentMetadataBundle bundle(
            String version,
            String digest,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Set<RuntimeContextType> contextTypes,
            Map<String, DomainSecurityConstraints> domainSecurityConstraints) {
        return bundle(version, digest, allowedCapabilityIds, allowedDomains, contextTypes,
                domainSecurityConstraints, "ACTIVE");
    }

    private static AgentMetadataBundle bundle(
            String version,
            String digest,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Set<RuntimeContextType> contextTypes,
            Map<String, DomainSecurityConstraints> domainSecurityConstraints,
            String activePayloadKeyId) {
        AgentProfileVersionKey profileKey = new AgentProfileVersionKey("agent-default", "profile-v1");
        ProfileBehaviorAssetRef assetRef = new ProfileBehaviorAssetRef("asset-default", "asset-v1");
        AgentProfileDefinition profile = new AgentProfileDefinition(
                profileKey,
                assetRef,
                allowedCapabilityIds,
                contextTypes,
                contextTypes,
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
        AgentPolicySnapshot policy = policy(
                allowedCapabilityIds,
                domainSecurityConstraints,
                contextTypes);
        return new AgentMetadataBundle(
                version,
                digest,
                "agent-default",
                Map.of("agent-default", "profile-v1"),
                policy.policyVersion(),
                new AgentSecuritySettings(Duration.ofHours(1), Duration.ofMinutes(5), 10, activePayloadKeyId),
                Map.of(profileKey, profile),
                Map.of(assetRef, asset),
                Map.of(policy.policyVersion(), policy));
    }

    public static AgentPolicySnapshot policy() {
        return policy(
                Set.of("query.search"),
                Map.of("employee", new DomainSecurityConstraints(Map.of())),
                Set.of(RuntimeContextType.QUERY));
    }

    private static AgentPolicySnapshot policy(
            Set<String> allowedCapabilityIds,
            Map<String, DomainSecurityConstraints> domainSecurityConstraints,
            Set<RuntimeContextType> contextTypes) {
        return new AgentPolicySnapshot(
                "policy-v1",
                Map.of("agent-default", new ProfileConstraints(
                        true,
                        allowedCapabilityIds,
                        contextTypes,
                        contextTypes,
                        Optional.of(AgentCapabilityRiskLevel.READ_ONLY),
                        Optional.of(AgentCapabilityExecutionMode.IMMEDIATE),
                        Optional.of(new BudgetLimits(Duration.ofSeconds(30), 1, 100, 100, 10_000)),
                        Optional.empty())),
                allowedCapabilityIds.stream()
                        .collect(java.util.stream.Collectors.toUnmodifiableMap(
                                capabilityId -> capabilityId,
                                capabilityId -> new CapabilityConstraints(true, Optional.empty()))),
                domainSecurityConstraints,
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

    public static UserPermission permissionWithQueryPreview(ExecutionSubjectRef subject) {
        return new UserPermission(
                subject,
                "perm-evidence-preview",
                "perm-v1",
                Set.of("query.search", "query.preview", "aggregate.compute"),
                Set.of("employee", "transaction"),
                Map.of(
                        "employee", Set.of("chineseName", "memberNo"),
                        "transaction", Set.of("transId", "amount")),
                Map.of(
                        "employee", Set.of("chineseName", "memberNo"),
                        "transaction", Set.of("transId", "amount")),
                Map.of(
                        "employee.chineseName", Set.of(com.dylan.agent.api.enums.AgentOperator.EQ),
                        "employee.memberNo", Set.of(com.dylan.agent.api.enums.AgentOperator.EQ),
                        "transaction.transId", Set.of(com.dylan.agent.api.enums.AgentOperator.EQ),
                        "transaction.amount", Set.of(
                                com.dylan.agent.api.enums.AgentOperator.EQ,
                                com.dylan.agent.api.enums.AgentOperator.GT,
                                com.dylan.agent.api.enums.AgentOperator.LT)),
                Map.of("transaction.amount", Set.of("sum")),
                Set.of("QUERY", "AGGREGATE"),
                Set.of("QUERY", "AGGREGATE"),
                Map.of(),
                NOW);
    }
}
