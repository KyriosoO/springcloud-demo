package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.model.MaskType;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Execution 阶段与当前的权限交集范围。
 */
public final class ExecutionScope {

    private final String subjectRef;
    private final DomainMetadataEvidence domainMetadataEvidence;
    private final Instant recheckedAt;
    private final String currentPermissionEvidenceId;
    private final String currentPermissionVersion;
    private final String currentPolicyVersion;
    private final Set<String> allowedCapabilityIds;
    private final Set<String> allowedDomains;
    private final Map<String, Set<String>> allowedFields;
    private final Map<String, MaskType> fieldMasks; // domain.field -> mask type
    private final Duration maxTotalDuration;
    private final int maxRepairAttempts;
    private final int maxResultRows;
    private final long maxResultBytes;

    public ExecutionScope(
            String subjectRef,
            DomainMetadataEvidence domainMetadataEvidence,
            Instant recheckedAt,
            String currentPermissionEvidenceId,
            String currentPermissionVersion,
            String currentPolicyVersion,
            Set<String> allowedCapabilityIds, Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields, Map<String, MaskType> fieldMasks,
            Duration maxTotalDuration,
            int maxRepairAttempts,
            int maxResultRows,
            long maxResultBytes) {
        this.subjectRef = requireNonBlank(subjectRef, "subjectRef");
        this.domainMetadataEvidence = Objects.requireNonNull(domainMetadataEvidence);
        this.recheckedAt = Objects.requireNonNull(recheckedAt);
        this.currentPermissionEvidenceId = requireNonBlank(
                currentPermissionEvidenceId, "currentPermissionEvidenceId");
        this.currentPermissionVersion = requireNonBlank(
                currentPermissionVersion, "currentPermissionVersion");
        this.currentPolicyVersion = requireNonBlank(currentPolicyVersion, "currentPolicyVersion");
        this.allowedCapabilityIds = copyNonBlankSet(allowedCapabilityIds, "allowedCapabilityIds");
        this.allowedDomains = copyNonBlankSet(allowedDomains, "allowedDomains");
        this.allowedFields = copyAllowedFields(allowedFields);
        this.fieldMasks = copyFieldMasks(fieldMasks);
        this.maxTotalDuration = requirePositive(maxTotalDuration, "maxTotalDuration");
        if (maxRepairAttempts < 0) {
            throw new IllegalArgumentException("maxRepairAttempts must be non-negative");
        }
        if (maxResultRows < 0) {
            throw new IllegalArgumentException("maxResultRows must be non-negative");
        }
        if (maxResultBytes < 0) {
            throw new IllegalArgumentException("maxResultBytes must be non-negative");
        }
        this.maxRepairAttempts = maxRepairAttempts;
        this.maxResultRows = maxResultRows;
        this.maxResultBytes = maxResultBytes;
    }

    public String subjectRef() { return subjectRef; }
    public DomainMetadataEvidence domainMetadataEvidence() { return domainMetadataEvidence; }
    public Instant recheckedAt() { return recheckedAt; }
    public String currentPermissionEvidenceId() { return currentPermissionEvidenceId; }
    public String currentPermissionVersion() { return currentPermissionVersion; }
    public String currentPolicyVersion() { return currentPolicyVersion; }
    public Set<String> allowedCapabilityIds() { return allowedCapabilityIds; }
    public Set<String> allowedDomains() { return allowedDomains; }
    public Map<String, Set<String>> allowedFields() { return allowedFields; }
    public Map<String, MaskType> fieldMasks() { return fieldMasks; }
    public Duration maxTotalDuration() { return maxTotalDuration; }
    public int maxRepairAttempts() { return maxRepairAttempts; }
    public int maxResultRows() { return maxResultRows; }
    public long maxResultBytes() { return maxResultBytes; }

    private static Duration requirePositive(Duration value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        if (value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
    }

    private static Map<String, Set<String>> copyAllowedFields(Map<String, Set<String>> source) {
        Objects.requireNonNull(source, "allowedFields must not be null");
        return source.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(
                        entry -> requireNonBlank(entry.getKey(), "allowed field key"),
                        entry -> copyNonBlankSet(entry.getValue(), "allowed field values")));
    }

    private static Map<String, MaskType> copyFieldMasks(Map<String, MaskType> source) {
        Objects.requireNonNull(source, "fieldMasks must not be null");
        return source.entrySet().stream()
                .collect(Collectors.toUnmodifiableMap(
                        entry -> requireNonBlank(entry.getKey(), "field mask key"),
                        entry -> Objects.requireNonNull(entry.getValue(), "field mask value must not be null")));
    }

    private static Set<String> copyNonBlankSet(Set<String> source, String name) {
        Objects.requireNonNull(source, name + " must not be null");
        return source.stream()
                .map(value -> requireNonBlank(value, name + " element"))
                .collect(Collectors.toUnmodifiableSet());
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
