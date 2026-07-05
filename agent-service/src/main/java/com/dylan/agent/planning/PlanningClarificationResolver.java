package com.dylan.agent.planning;

import com.dylan.agent.api.contract.runtime.clarification.CapabilityChoiceArgs;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.clarification.DomainChoiceArgs;
import com.dylan.agent.api.contract.runtime.clarification.FieldChoiceArgs;
import com.dylan.agent.api.contract.runtime.clarification.ValueChoiceArgs;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.ResolvedClarification;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * 将 Runtime 强类型澄清输出转换为 Java 持有的 CLARIFY 结果。
 */
public final class PlanningClarificationResolver {

    public ResolvedClarification routeClarification(
            ClarificationRequired clarification,
            String authorizationEvidenceRef,
            String domainMetadataEvidenceRef,
            PlanningOperationAudit routeAudit,
            java.time.Instant absoluteDeadline) {
        return base(clarification, authorizationEvidenceRef, domainMetadataEvidenceRef, routeAudit, absoluteDeadline)
                .stage(ResolvedClarification.ClarificationStage.ROUTE)
                .safeQuestion(safeQuestion(clarification))
                .build();
    }

    public ResolvedClarification planClarification(
            ClarificationRequired clarification,
            ValidatedRouteDecision routeDecision,
            String registrationIdentity,
            String authorizationEvidenceRef,
            String domainMetadataEvidenceRef,
            PlanningOperationAudit routeAudit,
            PlanningOperationAudit planAudit,
            java.time.Instant absoluteDeadline) {
        Objects.requireNonNull(routeDecision, "routeDecision must not be null");
        return base(clarification, authorizationEvidenceRef, domainMetadataEvidenceRef, routeAudit, absoluteDeadline)
                .stage(ResolvedClarification.ClarificationStage.PLAN)
                .capabilityId(routeDecision.capability().capabilityId())
                .domain(routeDecision.domain().orElse(null))
                .registrationIdentity(registrationIdentity)
                .planAudit(planAudit)
                .safeQuestion(safeQuestion(clarification))
                .build();
    }

    private static ResolvedClarification.Builder base(
            ClarificationRequired clarification,
            String authorizationEvidenceRef,
            String domainMetadataEvidenceRef,
            PlanningOperationAudit routeAudit,
            java.time.Instant absoluteDeadline) {
        Objects.requireNonNull(clarification, "clarification must not be null");
        return ResolvedClarification.builder()
                .requestCorrelationId(clarification.getRequestId())
                .reasonCode(clarification.getReasonCode())
                .args(clarification.getArgs())
                .authorizationEvidenceRef(authorizationEvidenceRef)
                .domainMetadataEvidenceRef(domainMetadataEvidenceRef)
                .contextSnapshotRefs(List.of())
                .routeAudit(routeAudit)
                .absoluteDeadline(absoluteDeadline);
    }

    private static String safeQuestion(ClarificationRequired clarification) {
        return switch (clarification.getReasonCode()) {
            case CAPABILITY_AMBIGUOUS -> "请确认要执行的能力：" + joinCapabilities(clarification);
            case DOMAIN_REQUIRED -> "请确认要查询的领域：" + joinDomains(clarification);
            case DOMAIN_AMBIGUOUS -> "请确认具体领域：" + joinDomains(clarification);
            case FIELD_REQUIRED -> "请补充需要使用的字段：" + joinFields(clarification);
            case FIELD_FORBIDDEN -> "没有权限访问请求的字段，请调整字段后重试。";
            case VALUE_REQUIRED -> "请补充字段 `" + valueField(clarification) + "` 的取值。";
            case VALUE_AMBIGUOUS -> "请确认字段 `" + valueField(clarification) + "` 的取值：" + joinValues(clarification);
        };
    }

    private static String joinCapabilities(ClarificationRequired clarification) {
        if (clarification.getArgs() instanceof CapabilityChoiceArgs args) {
            return String.join(", ", args.getCapabilityIds());
        }
        return "候选能力";
    }

    private static String joinDomains(ClarificationRequired clarification) {
        if (clarification.getArgs() instanceof DomainChoiceArgs args) {
            return String.join(", ", args.getDomains());
        }
        return "候选领域";
    }

    private static String joinFields(ClarificationRequired clarification) {
        if (clarification.getArgs() instanceof FieldChoiceArgs args) {
            return String.join(", ", args.getFields());
        }
        return "候选字段";
    }

    private static String joinValues(ClarificationRequired clarification) {
        if (clarification.getArgs() instanceof ValueChoiceArgs args) {
            return String.join(", ", args.getValues());
        }
        return "候选取值";
    }

    private static String valueField(ClarificationRequired clarification) {
        if (clarification.getArgs() instanceof ValueChoiceArgs args) {
            return Optional.ofNullable(args.getField()).orElse("目标字段");
        }
        return "目标字段";
    }
}
