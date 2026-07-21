package com.dylan.agent.metadata;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.metadata.authorization.model.UserPermission;
import com.dylan.agent.metadata.config.AgentMetadataBundle;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.policy.model.AgentPolicySnapshot;
import com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContributions;
import com.dylan.agent.metadata.policy.model.CapabilityConstraints;
import com.dylan.agent.metadata.policy.model.DomainSecurityConstraints;
import com.dylan.agent.metadata.policy.model.ProfileConstraints;
import com.dylan.agent.metadata.profile.model.AgentProfileDefinition;
import com.dylan.agent.metadata.profile.model.AgentProfileVersionKey;
import com.dylan.agent.metadata.profile.model.PlanningBudgetLimits;
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
        throw new UnsupportedOperationException("payload key 已移出 metadata bundle");
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
                Map.of("employee", new DomainSecurityConstraints(Set.of(), fields)));
    }

    private static AgentMetadataBundle bundle(
            String version,
            String digest,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Set<RuntimeContextType> contextTypes) {
        return bundle(
                version,
                digest,
                allowedCapabilityIds,
                allowedDomains,
                contextTypes,
                allowedDomains.stream()
                        .collect(java.util.stream.Collectors.toUnmodifiableMap(
                                domain -> domain,
                                domain -> new DomainSecurityConstraints(Set.of(), Map.of()))));
    }

    private static AgentMetadataBundle bundle(
            String version,
            String digest,
            Set<String> allowedCapabilityIds,
            Set<String> allowedDomains,
            Set<RuntimeContextType> contextTypes,
            Map<String, DomainSecurityConstraints> domainSecurityConstraints) {
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
                new PlanningBudgetLimits(Duration.ofSeconds(30), 1),
                standardContribution(
                        com.dylan.agent.metadata.authorization.resource.ResourceLimitSource.PROFILE,
                        "test-profile"));
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
                Map.of(profileKey, profile),
                Map.of(assetRef, asset),
                Map.of(policy.policyVersion(), policy));
    }

    public static AgentPolicySnapshot policy() {
        return policy(
                Set.of("query.search"),
                Map.of("employee", new DomainSecurityConstraints(Set.of(), Map.of())),
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
                        Optional.of(new PlanningBudgetLimits(Duration.ofSeconds(30), 1)))),
                allowedCapabilityIds.stream()
                        .collect(java.util.stream.Collectors.toUnmodifiableMap(
                                capabilityId -> capabilityId,
                                capabilityId -> new CapabilityConstraints(true))),
                domainSecurityConstraints,
                new PlanningBudgetLimits(Duration.ofSeconds(30), 1),
                standardContribution(
                        com.dylan.agent.metadata.authorization.resource.ResourceLimitSource.POLICY,
                        "test-policy"),
                Duration.ofHours(1),
                Set.of());
    }

    private static CapabilityResourceLimitContributions standardContribution(
            com.dylan.agent.metadata.authorization.resource.ResourceLimitSource source,
            String evidenceRef) {
        var limit = new com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit(
                100, 100, 10_000);
        return CapabilityResourceLimitContributions.of(java.util.List.of(
                new com.dylan.agent.metadata.authorization.resource.CapabilityResourceLimitContribution<>(
                        source,
                        com.dylan.agent.api.contract.common.AgentExecutionContracts.STANDARD_RESOURCE_LIMIT,
                        com.dylan.agent.adapter.api.operation.StandardCapabilityResourceLimit.class,
                        limit,
                        evidenceRef)));
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
