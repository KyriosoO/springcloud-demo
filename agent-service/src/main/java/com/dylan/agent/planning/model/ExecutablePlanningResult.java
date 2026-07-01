package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;

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
    private final String capabilityId;
    private final Optional<String> domain;
    private final AgentPlanKind planKind;
    private final Object resolvedRegistration; // ResolvedRegistration after D02_01
    private final AgentPlan rawPlan;
    private final Object authorizationSnapshot; // AuthorizationSnapshot after D02_03
    private final List<Object> contextSnapshots; // List<ContextSnapshot> after D02_03
    private final PlanningOperationAudit routeAudit;
    private final PlanningOperationAudit planAudit;
    private final Instant absoluteDeadline;

    private ExecutablePlanningResult(Builder builder) {
        this.requestCorrelationId = Objects.requireNonNull(builder.requestCorrelationId);
        this.capabilityId = Objects.requireNonNull(builder.capabilityId);
        this.domain = Optional.ofNullable(builder.domain);
        this.planKind = Objects.requireNonNull(builder.planKind);
        this.resolvedRegistration = Objects.requireNonNull(builder.resolvedRegistration);
        this.rawPlan = Objects.requireNonNull(builder.rawPlan);
        this.authorizationSnapshot = Objects.requireNonNull(builder.authorizationSnapshot);
        this.contextSnapshots = List.copyOf(
                builder.contextSnapshots != null ? builder.contextSnapshots : List.of());
        this.routeAudit = Objects.requireNonNull(builder.routeAudit);
        this.planAudit = Objects.requireNonNull(builder.planAudit);
        this.absoluteDeadline = Objects.requireNonNull(builder.absoluteDeadline);
    }

    // ── PlanningResult ──

    @Override
    public String requestCorrelationId() {
        return requestCorrelationId;
    }

    @Override
    public Instant absoluteDeadline() {
        return absoluteDeadline;
    }

    // ── getters ──

    public String capabilityId() {
        return capabilityId;
    }

    public Optional<String> domain() {
        return domain;
    }

    public AgentPlanKind planKind() {
        return planKind;
    }

    public Object resolvedRegistration() {
        return resolvedRegistration;
    }

    public AgentPlan rawPlan() {
        return rawPlan;
    }

    public Object authorizationSnapshot() {
        return authorizationSnapshot;
    }

    public List<Object> contextSnapshots() {
        return contextSnapshots;
    }

    public PlanningOperationAudit routeAudit() {
        return routeAudit;
    }

    public PlanningOperationAudit planAudit() {
        return planAudit;
    }

    // ── Builder ──

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private String requestCorrelationId;
        private String capabilityId;
        private String domain;
        private AgentPlanKind planKind;
        private Object resolvedRegistration;
        private AgentPlan rawPlan;
        private Object authorizationSnapshot;
        private List<Object> contextSnapshots;
        private PlanningOperationAudit routeAudit;
        private PlanningOperationAudit planAudit;
        private Instant absoluteDeadline;

        public Builder requestCorrelationId(String v) { this.requestCorrelationId = v; return this; }
        public Builder capabilityId(String v) { this.capabilityId = v; return this; }
        public Builder domain(String v) { this.domain = v; return this; }
        public Builder planKind(AgentPlanKind v) { this.planKind = v; return this; }
        public Builder resolvedRegistration(Object v) { this.resolvedRegistration = v; return this; }
        public Builder rawPlan(AgentPlan v) { this.rawPlan = v; return this; }
        public Builder authorizationSnapshot(Object v) { this.authorizationSnapshot = v; return this; }
        public Builder contextSnapshots(List<Object> v) { this.contextSnapshots = v; return this; }
        public Builder routeAudit(PlanningOperationAudit v) { this.routeAudit = v; return this; }
        public Builder planAudit(PlanningOperationAudit v) { this.planAudit = v; return this; }
        public Builder absoluteDeadline(Instant v) { this.absoluteDeadline = v; return this; }

        public ExecutablePlanningResult build() {
            return new ExecutablePlanningResult(this);
        }
    }
}
