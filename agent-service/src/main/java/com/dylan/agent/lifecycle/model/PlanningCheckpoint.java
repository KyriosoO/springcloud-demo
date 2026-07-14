package com.dylan.agent.lifecycle.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningOperationAudit;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * Core 进入前的不可变 Planning 事实固化，由 D02_02 唯一负责。
 */
public final class PlanningCheckpoint {

    private final String invocationId;
    private final String requestCorrelationId;
    private final String capabilityId;
    private final String domain;
    private final String planKind;
    private final String registrationIdentity;
    private final String planningArtifactBindingDigest;
    private final PlanningOperationAudit routeAudit;
    private final PlanningOperationAudit planAudit;
    private final String authorizationSnapshotRef;
    private final List<ContextSnapshotRef> contextSnapshotRefs;
    private final String checkpointHash;

    private PlanningCheckpoint(Builder builder) {
        this.invocationId = requireNonBlank(builder.invocationId, "invocationId");
        this.requestCorrelationId = requireNonBlank(builder.requestCorrelationId, "requestCorrelationId");
        this.capabilityId = requireNonBlank(builder.capabilityId, "capabilityId");
        this.domain = normalizeOptional(builder.domain, "domain");
        this.planKind = requireNonBlank(builder.planKind, "planKind");
        this.registrationIdentity = requireNonBlank(builder.registrationIdentity, "registrationIdentity");
        this.planningArtifactBindingDigest = requireSha256(
                builder.planningArtifactBindingDigest, "planningArtifactBindingDigest");
        this.routeAudit = Objects.requireNonNull(builder.routeAudit);
        this.planAudit = Objects.requireNonNull(builder.planAudit);
        this.authorizationSnapshotRef = requireNonBlank(builder.authorizationSnapshotRef, "authorizationSnapshotRef");
        this.contextSnapshotRefs = normalizeContextSnapshotRefs(builder.contextSnapshotRefs);
        this.checkpointHash = computeHash();
    }

    public static PlanningCheckpoint from(InvocationHandle handle,
                                          ExecutablePlanningResult result) {
        return new Builder()
                .invocationId(handle.invocationId())
                .requestCorrelationId(result.requestCorrelationId())
                .capabilityId(result.capabilityId())
                .domain(result.domain().orElse(null))
                .planKind(result.planKind().name())
                .registrationIdentity(result.resolvedRegistration().registrationIdentity())
                .planningArtifactBindingDigest(result.artifactIdentity().bindingDigest())
                .routeAudit(result.routeAudit())
                .planAudit(result.planAudit())
                .authorizationSnapshotRef(result.authorizationSnapshot().snapshotId())
                .contextSnapshotRefs(contextSnapshotRefs(result.contextSnapshots()))
                .build();
    }

    private static List<ContextSnapshotRef> contextSnapshotRefs(List<ContextSnapshot> snapshots) {
        return snapshots.stream()
                .map(PlanningCheckpoint::contextSnapshotRef)
                .toList();
    }

    private static ContextSnapshotRef contextSnapshotRef(ContextSnapshot snapshot) {
        return new ContextSnapshotRef(
                snapshot.contextId(),
                snapshot.contextType(),
                snapshot.sourceDomain(),
                snapshot.storedContractRef(),
                snapshot.effectiveContractRef(),
                snapshot.recordVersion());
    }

    private static List<ContextSnapshotRef> normalizeContextSnapshotRefs(List<ContextSnapshotRef> refs) {
        List<ContextSnapshotRef> normalized = refs == null ? List.of() : refs.stream()
                .sorted(Comparator.comparing(ref -> ref.contextType().name()))
                .toList();
        HashSet<RuntimeContextType> seen = new HashSet<>();
        for (ContextSnapshotRef ref : normalized) {
            if (!seen.add(ref.contextType())) {
                throw new IllegalArgumentException(
                        "contextSnapshotRefs must not contain duplicate contextType: " + ref.contextType());
            }
        }
        return List.copyOf(normalized);
    }

    private static String contractRef(ContractRef ref) {
        return ref.namespace() + ":" + ref.name() + ":" + ref.version();
    }

    private String computeHash() {
        String content = invocationId + "|" + requestCorrelationId + "|" + capabilityId
                + "|" + domain + "|" + planKind + "|" + registrationIdentity
                + "|" + planningArtifactBindingDigest
                + "|" + canonicalAudit(routeAudit) + "|" + canonicalAudit(planAudit)
                + "|" + authorizationSnapshotRef + "|" + canonicalContextRefs();
        return sha256Hex(content);
    }

    private static String canonicalAudit(PlanningOperationAudit audit) {
        StringBuilder builder = new StringBuilder()
                .append(audit.operation().name()).append('|')
                .append(audit.metadataStatus().name()).append('|')
                .append(audit.localDurationMs()).append('|')
                .append(audit.termination().name());
        audit.runtimeMetadata().ifPresent(metadata -> builder.append('|').append(canonicalRuntimeMetadata(metadata)));
        return builder.toString();
    }

    private static String canonicalRuntimeMetadata(RuntimeOperationMetadata metadata) {
        return metadata.getOperation().name()
                + "|" + metadata.getProviderAttempts()
                + "|" + metadata.getRepairAttempts()
                + "|" + metadata.getRepairDurationMs()
                + "|" + metadata.getTotalDurationMs()
                + "|" + metadata.getTerminationReason().name()
                + "|" + metadata.getDeadlineReached()
                + "|" + metadata.getRepairLimitReached();
    }

    private String canonicalContextRefs() {
        StringBuilder builder = new StringBuilder("[");
        for (int i = 0; i < contextSnapshotRefs.size(); i++) {
            ContextSnapshotRef ref = contextSnapshotRefs.get(i);
            if (i > 0) {
                builder.append(',');
            }
            builder.append(ref.contextId()).append('|')
                    .append(ref.contextType().name()).append('|')
                    .append(ref.sourceDomain().orElse("")).append('|')
                    .append(contractRef(ref.storedContractRef())).append('|')
                    .append(contractRef(ref.effectiveContractRef())).append('|')
                    .append(ref.recordVersion());
        }
        return builder.append(']').toString();
    }

    private static String sha256Hex(String content) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(content.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static String normalizeOptional(String value, String name) {
        if (value == null) {
            return null;
        }
        return requireNonBlank(value, name);
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }

    private static String requireSha256(String value, String name) {
        String normalized = requireNonBlank(value, name);
        if (!normalized.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256 hex");
        }
        return normalized;
    }

    // ── 只读访问器 ──
    public String invocationId() { return invocationId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public String capabilityId() { return capabilityId; }
    public String domain() { return domain; }
    public String planKind() { return planKind; }
    public String registrationIdentity() { return registrationIdentity; }
    public String planningArtifactBindingDigest() { return planningArtifactBindingDigest; }
    public PlanningOperationAudit routeAudit() { return routeAudit; }
    public PlanningOperationAudit planAudit() { return planAudit; }
    public String authorizationSnapshotRef() { return authorizationSnapshotRef; }
    public List<ContextSnapshotRef> contextSnapshotRefs() { return contextSnapshotRefs; }
    public String checkpointHash() { return checkpointHash; }

    /**
     * Context snapshot 的安全审计引用；只记录身份、类型、schema 与版本，不包含 payload。
     */
    public record ContextSnapshotRef(
            String contextId,
            RuntimeContextType contextType,
            Optional<String> sourceDomain,
            ContractRef storedContractRef,
            ContractRef effectiveContractRef,
            long recordVersion) {
        public ContextSnapshotRef {
            Objects.requireNonNull(contextId);
            Objects.requireNonNull(contextType);
            sourceDomain = Objects.requireNonNull(sourceDomain);
            Objects.requireNonNull(storedContractRef);
            Objects.requireNonNull(effectiveContractRef);
            if (contextId.isBlank()) {
                throw new IllegalArgumentException("contextId must not be blank");
            }
            sourceDomain.ifPresent(domain -> {
                if (domain.isBlank()) {
                    throw new IllegalArgumentException("sourceDomain must not be blank when present");
                }
            });
            if (recordVersion < 0) {
                throw new IllegalArgumentException("recordVersion must be non-negative");
            }
        }
    }

    public static final class Builder {
        private String invocationId;
        private String requestCorrelationId;
        private String capabilityId;
        private String domain;
        private String planKind;
        private String registrationIdentity;
        private String planningArtifactBindingDigest;
        private PlanningOperationAudit routeAudit;
        private PlanningOperationAudit planAudit;
        private String authorizationSnapshotRef;
        private List<ContextSnapshotRef> contextSnapshotRefs;

        public Builder invocationId(String v) { this.invocationId = v; return this; }
        public Builder requestCorrelationId(String v) { this.requestCorrelationId = v; return this; }
        public Builder capabilityId(String v) { this.capabilityId = v; return this; }
        public Builder domain(String v) { this.domain = v; return this; }
        public Builder planKind(String v) { this.planKind = v; return this; }
        public Builder registrationIdentity(String v) { this.registrationIdentity = v; return this; }
        public Builder planningArtifactBindingDigest(String v) { this.planningArtifactBindingDigest = v; return this; }
        public Builder routeAudit(PlanningOperationAudit v) { this.routeAudit = v; return this; }
        public Builder planAudit(PlanningOperationAudit v) { this.planAudit = v; return this; }
        public Builder authorizationSnapshotRef(String v) { this.authorizationSnapshotRef = v; return this; }
        public Builder contextSnapshotRefs(List<ContextSnapshotRef> v) { this.contextSnapshotRefs = v; return this; }

        public PlanningCheckpoint build() { return new PlanningCheckpoint(this); }
    }
}
