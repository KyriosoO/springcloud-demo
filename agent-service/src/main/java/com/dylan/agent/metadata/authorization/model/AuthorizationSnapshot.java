package com.dylan.agent.metadata.authorization.model;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.model.MaskType;

/**
 * Planning 时刻的版本化请求级授权证据。
 * 不包含 JWT 或完整权限表达式。
 */
public final class AuthorizationSnapshot {

    private final String snapshotId;
    private final String subjectRef;
    private final String profileVersion;
    private final String policyVersion;
    private final Set<String> allowedCapabilityIds;
    private final Set<String> allowedDomains;
    private final Map<String, Set<String>> allowedFields;
    private final Map<String, MaskType> fieldMasks;
    private final Instant snapshotTime;
    private final DomainMetadataEvidence domainMetadataEvidence;
    private final ExecutionBudget executionBudget;

    public AuthorizationSnapshot(
            String snapshotId, String subjectRef,
            String profileVersion, String policyVersion,
            Set<String> allowedCapabilityIds, Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields, Map<String, MaskType> fieldMasks,
            Instant snapshotTime,
            DomainMetadataEvidence domainMetadataEvidence,
            ExecutionBudget executionBudget) {
        this.snapshotId = Objects.requireNonNull(snapshotId);
        this.subjectRef = Objects.requireNonNull(subjectRef);
        this.profileVersion = Objects.requireNonNull(profileVersion);
        this.policyVersion = Objects.requireNonNull(policyVersion);
        this.allowedCapabilityIds = Set.copyOf(allowedCapabilityIds);
        this.allowedDomains = Set.copyOf(allowedDomains);
        this.allowedFields = Map.copyOf(allowedFields);
        this.fieldMasks = copyFieldMasks(fieldMasks);
        this.snapshotTime = Objects.requireNonNull(snapshotTime);
        this.domainMetadataEvidence = domainMetadataEvidence;
        this.executionBudget = Objects.requireNonNull(executionBudget, "executionBudget must not be null");
    }

    public String snapshotId() { return snapshotId; }
    public String subjectRef() { return subjectRef; }
    public String profileVersion() { return profileVersion; }
    public String policyVersion() { return policyVersion; }
    public Set<String> allowedCapabilityIds() { return allowedCapabilityIds; }
    public Set<String> allowedDomains() { return allowedDomains; }
    public Map<String, Set<String>> allowedFields() { return allowedFields; }
    public Map<String, MaskType> fieldMasks() { return fieldMasks; }
    public Instant snapshotTime() { return snapshotTime; }
    public Optional<DomainMetadataEvidence> domainMetadataEvidence() {
        return Optional.ofNullable(domainMetadataEvidence);
    }
    public ExecutionBudget executionBudget() { return executionBudget; }

    private static Map<String, MaskType> copyFieldMasks(Map<String, MaskType> source) {
        Objects.requireNonNull(source, "fieldMasks must not be null");
        return source.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(
                        entry -> requireNonBlank(entry.getKey(), "field mask key"),
                        entry -> Objects.requireNonNull(entry.getValue(), "field mask value must not be null")));
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
