package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationArgs;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Java 已校验的澄清终态，由 D02_00 唯一负责。
 *
 * <p>由 PlanningService 在 Route 或 Plan 阶段产生，经 Lifecycle 直接形成 CLARIFY 响应，
 * 不进入 Execution Core、Handler 或 Adapter。</p>
 */
public non-sealed class ResolvedClarification implements PlanningResult {

    private final String requestCorrelationId;
    private final ClarificationStage stage;
    private final ClarificationReasonCode reasonCode;
    private final ClarificationArgs args;
    private final String safeQuestion;
    private final Optional<String> capabilityId;
    private final Optional<String> domain;
    private final Optional<String> registrationIdentity;
    private final String authorizationEvidenceRef;
    private final String domainMetadataEvidenceRef;
    private final List<String> contextSnapshotRefs;
    private final PlanningOperationAudit routeAudit;
    private final Optional<PlanningOperationAudit> planAudit;
    private final Instant absoluteDeadline;

    private ResolvedClarification(Builder builder) {
        this.requestCorrelationId = java.util.Objects.requireNonNull(builder.requestCorrelationId);
        this.stage = java.util.Objects.requireNonNull(builder.stage);
        this.reasonCode = java.util.Objects.requireNonNull(builder.reasonCode);
        this.args = java.util.Objects.requireNonNull(builder.args);
        this.safeQuestion = java.util.Objects.requireNonNull(builder.safeQuestion);
        this.capabilityId = Optional.ofNullable(builder.capabilityId);
        this.domain = Optional.ofNullable(builder.domain);
        this.registrationIdentity = Optional.ofNullable(builder.registrationIdentity);
        this.authorizationEvidenceRef = java.util.Objects.requireNonNull(builder.authorizationEvidenceRef);
        this.domainMetadataEvidenceRef = java.util.Objects.requireNonNull(builder.domainMetadataEvidenceRef);
        this.contextSnapshotRefs = List.copyOf(
                builder.contextSnapshotRefs == null ? List.of() : builder.contextSnapshotRefs);
        this.routeAudit = java.util.Objects.requireNonNull(builder.routeAudit);
        this.planAudit = Optional.ofNullable(builder.planAudit);
        this.absoluteDeadline = java.util.Objects.requireNonNull(builder.absoluteDeadline);
    }

    @Override
    public String requestCorrelationId() { return requestCorrelationId; }

    @Override
    public Instant absoluteDeadline() { return absoluteDeadline; }

    public ClarificationStage stage() { return stage; }
    public ClarificationReasonCode reasonCode() { return reasonCode; }
    public ClarificationArgs args() { return args; }
    public String safeQuestion() { return safeQuestion; }
    public Optional<String> capabilityId() { return capabilityId; }
    public Optional<String> domain() { return domain; }
    public Optional<String> registrationIdentity() { return registrationIdentity; }
    public String authorizationEvidenceRef() { return authorizationEvidenceRef; }
    public String domainMetadataEvidenceRef() { return domainMetadataEvidenceRef; }
    public List<String> contextSnapshotRefs() { return contextSnapshotRefs; }
    public PlanningOperationAudit routeAudit() { return routeAudit; }
    public Optional<PlanningOperationAudit> planAudit() { return planAudit; }

    public static Builder builder() { return new Builder(); }

    public static final class Builder {
        private String requestCorrelationId;
        private ClarificationStage stage;
        private ClarificationReasonCode reasonCode;
        private ClarificationArgs args;
        private String safeQuestion;
        private String capabilityId;
        private String domain;
        private String registrationIdentity;
        private String authorizationEvidenceRef;
        private String domainMetadataEvidenceRef;
        private List<String> contextSnapshotRefs;
        private PlanningOperationAudit routeAudit;
        private PlanningOperationAudit planAudit;
        private Instant absoluteDeadline;

        public Builder requestCorrelationId(String v) { this.requestCorrelationId = v; return this; }
        public Builder stage(ClarificationStage v) { this.stage = v; return this; }
        public Builder reasonCode(ClarificationReasonCode v) { this.reasonCode = v; return this; }
        public Builder args(ClarificationArgs v) { this.args = v; return this; }
        public Builder safeQuestion(String v) { this.safeQuestion = v; return this; }
        public Builder capabilityId(String v) { this.capabilityId = v; return this; }
        public Builder domain(String v) { this.domain = v; return this; }
        public Builder registrationIdentity(String v) { this.registrationIdentity = v; return this; }
        public Builder authorizationEvidenceRef(String v) { this.authorizationEvidenceRef = v; return this; }
        public Builder domainMetadataEvidenceRef(String v) { this.domainMetadataEvidenceRef = v; return this; }
        public Builder contextSnapshotRefs(List<String> v) { this.contextSnapshotRefs = v; return this; }
        public Builder routeAudit(PlanningOperationAudit v) { this.routeAudit = v; return this; }
        public Builder planAudit(PlanningOperationAudit v) { this.planAudit = v; return this; }
        public Builder absoluteDeadline(Instant v) { this.absoluteDeadline = v; return this; }

        public ResolvedClarification build() { return new ResolvedClarification(this); }
    }

    public enum ClarificationStage { ROUTE, PLAN }
}
