package com.dylan.agent.metadata.authorization.model;

import java.time.Instant;
import java.util.*;

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
    private final Instant snapshotTime;

    public AuthorizationSnapshot(
            String snapshotId, String subjectRef,
            String profileVersion, String policyVersion,
            Set<String> allowedCapabilityIds, Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields, Instant snapshotTime) {
        this.snapshotId = Objects.requireNonNull(snapshotId);
        this.subjectRef = Objects.requireNonNull(subjectRef);
        this.profileVersion = Objects.requireNonNull(profileVersion);
        this.policyVersion = Objects.requireNonNull(policyVersion);
        this.allowedCapabilityIds = Set.copyOf(allowedCapabilityIds);
        this.allowedDomains = Set.copyOf(allowedDomains);
        this.allowedFields = Map.copyOf(allowedFields);
        this.snapshotTime = Objects.requireNonNull(snapshotTime);
    }

    public String snapshotId() { return snapshotId; }
    public String subjectRef() { return subjectRef; }
    public String profileVersion() { return profileVersion; }
    public String policyVersion() { return policyVersion; }
    public Set<String> allowedCapabilityIds() { return allowedCapabilityIds; }
    public Set<String> allowedDomains() { return allowedDomains; }
    public Map<String, Set<String>> allowedFields() { return allowedFields; }
    public Instant snapshotTime() { return snapshotTime; }
}
