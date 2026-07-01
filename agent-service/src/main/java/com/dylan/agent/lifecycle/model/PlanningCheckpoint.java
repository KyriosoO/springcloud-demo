package com.dylan.agent.lifecycle.model;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningOperationAudit;

import java.util.Objects;

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
    private final PlanningOperationAudit routeAudit;
    private final PlanningOperationAudit planAudit;
    private final String authorizationSnapshotRef;
    private final String contextSnapshotRefs; // JSON-serialized safe ref list
    private final String checkpointHash;

    private PlanningCheckpoint(Builder builder) {
        this.invocationId = Objects.requireNonNull(builder.invocationId);
        this.requestCorrelationId = Objects.requireNonNull(builder.requestCorrelationId);
        this.capabilityId = builder.capabilityId;
        this.domain = builder.domain;
        this.planKind = builder.planKind != null ? builder.planKind : "";
        this.registrationIdentity = builder.registrationIdentity;
        this.routeAudit = Objects.requireNonNull(builder.routeAudit);
        this.planAudit = Objects.requireNonNull(builder.planAudit);
        this.authorizationSnapshotRef = Objects.requireNonNull(builder.authorizationSnapshotRef);
        this.contextSnapshotRefs = builder.contextSnapshotRefs != null ? builder.contextSnapshotRefs : "[]";
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
                .registrationIdentity("reg-" + result.capabilityId())
                .routeAudit(result.routeAudit())
                .planAudit(result.planAudit())
                .authorizationSnapshotRef("auth-" + handle.invocationId())
                .build();
    }

    private String computeHash() {
        String content = invocationId + "|" + requestCorrelationId + "|" + capabilityId
                + "|" + domain + "|" + planKind + "|" + registrationIdentity;
        // canonical SHA-256 placeholder; D03 replaces with real digest
        return Integer.toHexString(content.hashCode());
    }

    // ── 只读访问器 ──
    public String invocationId() { return invocationId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public String capabilityId() { return capabilityId; }
    public String domain() { return domain; }
    public String planKind() { return planKind; }
    public String registrationIdentity() { return registrationIdentity; }
    public PlanningOperationAudit routeAudit() { return routeAudit; }
    public PlanningOperationAudit planAudit() { return planAudit; }
    public String authorizationSnapshotRef() { return authorizationSnapshotRef; }
    public String contextSnapshotRefs() { return contextSnapshotRefs; }
    public String checkpointHash() { return checkpointHash; }

    public static final class Builder {
        private String invocationId;
        private String requestCorrelationId;
        private String capabilityId;
        private String domain;
        private String planKind;
        private String registrationIdentity;
        private PlanningOperationAudit routeAudit;
        private PlanningOperationAudit planAudit;
        private String authorizationSnapshotRef;
        private String contextSnapshotRefs;

        public Builder invocationId(String v) { this.invocationId = v; return this; }
        public Builder requestCorrelationId(String v) { this.requestCorrelationId = v; return this; }
        public Builder capabilityId(String v) { this.capabilityId = v; return this; }
        public Builder domain(String v) { this.domain = v; return this; }
        public Builder planKind(String v) { this.planKind = v; return this; }
        public Builder registrationIdentity(String v) { this.registrationIdentity = v; return this; }
        public Builder routeAudit(PlanningOperationAudit v) { this.routeAudit = v; return this; }
        public Builder planAudit(PlanningOperationAudit v) { this.planAudit = v; return this; }
        public Builder authorizationSnapshotRef(String v) { this.authorizationSnapshotRef = v; return this; }
        public Builder contextSnapshotRefs(String v) { this.contextSnapshotRefs = v; return this; }

        public PlanningCheckpoint build() { return new PlanningCheckpoint(this); }
    }
}
