package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.context.model.ContextSnapshot;

import java.time.Instant;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * 可执行 Planning 结果，由 D02_00 唯一负责。
 *
 * <p>携带 Resolved Registration、Authorization/Context Snapshot 和已校验 Raw Plan。
 * Lifecycle 接收后写入 checkpoint，然后交给 Execution Core。
 *
 * <p>构造器执行非业务结构校验（correlation 一致、planKind 与 Registration 一致、
 * Snapshot 主体/Scope 与 Handle 一致等），不调用 Validator/Handler/Adapter 或持久化。
 */
public non-sealed class ExecutablePlanningResult implements PlanningResult {

    private final String requestCorrelationId;
    private final String invocationId;
    private final String capabilityId;
    private final Optional<String> domain;
    private final AgentPlanKind planKind;
    private final ResolvedRegistration resolvedRegistration;
    private final AgentPlan rawPlan;
    private final AuthorizationSnapshot authorizationSnapshot;
    private final List<ContextSnapshot> contextSnapshots;
    private final PlanningOperationAudit routeAudit;
    private final PlanningOperationAudit planAudit;
    private final Instant absoluteDeadline;
    private final PlanningArtifactIdentity artifactIdentity;

    private ExecutablePlanningResult(Builder builder) {
        this.invocationId = Objects.requireNonNull(builder.invocationId);
        this.requestCorrelationId = Objects.requireNonNull(builder.requestCorrelationId);
        this.capabilityId = Objects.requireNonNull(builder.capabilityId);
        this.domain = Optional.ofNullable(normalizeDomain(builder.domain));
        this.planKind = Objects.requireNonNull(builder.planKind);
        this.resolvedRegistration = Objects.requireNonNull(builder.resolvedRegistration);
        this.rawPlan = Objects.requireNonNull(builder.rawPlan);
        this.authorizationSnapshot = Objects.requireNonNull(builder.authorizationSnapshot);
        this.contextSnapshots = List.copyOf(
                builder.contextSnapshots != null ? builder.contextSnapshots : List.of());
        this.routeAudit = Objects.requireNonNull(builder.routeAudit);
        this.planAudit = Objects.requireNonNull(builder.planAudit);
        this.absoluteDeadline = Objects.requireNonNull(builder.absoluteDeadline);
        validateInvariants();
        this.artifactIdentity = PlanningArtifactCanonicalizer.create(this);
    }

    private void validateInvariants() {
        resolvedRegistration.validateIdentity();
        if (!capabilityId.equals(resolvedRegistration.capabilityId())) {
            throw new IllegalArgumentException("capabilityId must match resolvedRegistration");
        }
        if (planKind != resolvedRegistration.planKind()) {
            throw new IllegalArgumentException("planKind must match resolvedRegistration");
        }
        if (rawPlan.getPlanKind() != planKind) {
            throw new IllegalArgumentException("rawPlan planKind must match planning result");
        }
        if (!resolvedRegistration.registration().rawPlanType().isInstance(rawPlan)) {
            throw new IllegalArgumentException("rawPlan type must match resolvedRegistration");
        }
        if (routeAudit.operation() != RuntimeOperationType.ROUTE) {
            throw new IllegalArgumentException("routeAudit must be ROUTE");
        }
        if (planAudit.operation() != RuntimeOperationType.PLAN) {
            throw new IllegalArgumentException("planAudit must be PLAN");
        }
    }

    private static String normalizeDomain(String domain) {
        if (domain == null) {
            return null;
        }
        if (domain.isBlank()) {
            throw new IllegalArgumentException("domain must not be blank");
        }
        return domain.trim();
    }

    // ── PlanningResult 接口方法 ──

    @Override
    public String requestCorrelationId() {
        return requestCorrelationId;
    }

    @Override
    public Instant absoluteDeadline() {
        return absoluteDeadline;
    }

    // ── 只读访问方法 ──

    public String capabilityId() {
        return capabilityId;
    }

    public String invocationId() { return invocationId; }

    public PlanningArtifactIdentity artifactIdentity() { return artifactIdentity; }

    public boolean hasValidArtifactIdentity() {
        return PlanningArtifactCanonicalizer.matches(this);
    }

    public Optional<String> domain() {
        return domain;
    }

    public AgentPlanKind planKind() {
        return planKind;
    }

    public ResolvedRegistration resolvedRegistration() {
        return resolvedRegistration;
    }

    public AgentPlan rawPlan() {
        return rawPlan;
    }

    public AuthorizationSnapshot authorizationSnapshot() {
        return authorizationSnapshot;
    }

    public List<ContextSnapshot> contextSnapshots() {
        return contextSnapshots;
    }

    public PlanningOperationAudit routeAudit() {
        return routeAudit;
    }

    public PlanningOperationAudit planAudit() {
        return planAudit;
    }

    // ── 构建器 ──

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String requestCorrelationId;
        private String invocationId;
        private String capabilityId;
        private String domain;
        private AgentPlanKind planKind;
        private ResolvedRegistration resolvedRegistration;
        private AgentPlan rawPlan;
        private AuthorizationSnapshot authorizationSnapshot;
        private List<ContextSnapshot> contextSnapshots;
        private PlanningOperationAudit routeAudit;
        private PlanningOperationAudit planAudit;
        private Instant absoluteDeadline;

        public Builder requestCorrelationId(String v) { this.requestCorrelationId = v; return this; }
        public Builder invocationId(String v) { this.invocationId = v; return this; }
        public Builder capabilityId(String v) { this.capabilityId = v; return this; }
        public Builder domain(String v) { this.domain = v; return this; }
        public Builder planKind(AgentPlanKind v) { this.planKind = v; return this; }
        public Builder resolvedRegistration(ResolvedRegistration v) { this.resolvedRegistration = v; return this; }
        public Builder rawPlan(AgentPlan v) { this.rawPlan = v; return this; }
        public Builder authorizationSnapshot(AuthorizationSnapshot v) { this.authorizationSnapshot = v; return this; }
        public Builder contextSnapshots(List<ContextSnapshot> v) { this.contextSnapshots = v; return this; }
        public Builder routeAudit(PlanningOperationAudit v) { this.routeAudit = v; return this; }
        public Builder planAudit(PlanningOperationAudit v) { this.planAudit = v; return this; }
        public Builder absoluteDeadline(Instant v) { this.absoluteDeadline = v; return this; }

        public ExecutablePlanningResult build() {
            return new ExecutablePlanningResult(this);
        }
    }
}
