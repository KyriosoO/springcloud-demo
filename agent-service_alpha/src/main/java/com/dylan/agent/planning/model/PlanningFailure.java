package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * D02_00 拥有的内部不可变 Planning 失败值。
 *
 * <p>该类型不是 Runtime 响应，也不携带 provider 原始消息、payload、
 * 权限事实、堆栈或 API 响应正文。</p>
 */
public final class PlanningFailure {

    private final String requestCorrelationId;
    private final PlanningStage stage;
    private final KernelErrorCode errorCode;
    private final String diagnosticId;
    private final String safeMessage;
    private final String authorizationEvidenceRef;
    private final String domainMetadataEvidenceRef;
    private final List<PlanningOperationAudit> operationAudits;

    public PlanningFailure(String requestCorrelationId,
                           PlanningStage stage,
                           KernelErrorCode errorCode,
                           String diagnosticId,
                           String authorizationEvidenceRef,
                           String domainMetadataEvidenceRef,
                           List<PlanningOperationAudit> operationAudits) {
        this(requestCorrelationId, stage, errorCode, diagnosticId, null,
                authorizationEvidenceRef, domainMetadataEvidenceRef, operationAudits);
    }

    public PlanningFailure(String requestCorrelationId,
                           PlanningStage stage,
                           KernelErrorCode errorCode,
                           String diagnosticId,
                           String safeMessage,
                           String authorizationEvidenceRef,
                           String domainMetadataEvidenceRef,
                           List<PlanningOperationAudit> operationAudits) {
        this.requestCorrelationId = requireText(requestCorrelationId, "requestCorrelationId");
        this.stage = Objects.requireNonNull(stage, "stage must not be null");
        this.errorCode = Objects.requireNonNull(errorCode, "errorCode must not be null");
        this.diagnosticId = requireText(diagnosticId, "diagnosticId");
        this.safeMessage = normalizeOptionalSafeMessage(safeMessage);
        this.authorizationEvidenceRef = normalizeOptionalRef(authorizationEvidenceRef, "authorizationEvidenceRef");
        this.domainMetadataEvidenceRef = normalizeOptionalRef(domainMetadataEvidenceRef, "domainMetadataEvidenceRef");
        this.operationAudits = List.copyOf(operationAudits == null ? List.of() : operationAudits);
        validateInvariants();
    }

    public static PlanningFailure historyProjection(String requestCorrelationId,
                                                    KernelErrorCode errorCode,
                                                    String diagnosticId) {
        if (errorCode != KernelErrorCode.PERSISTENCE_FAILED
                && errorCode != KernelErrorCode.INTERNAL_ERROR) {
            throw new IllegalArgumentException("history projection only allows persistence/internal failures");
        }
        return new PlanningFailure(
                requestCorrelationId,
                PlanningStage.HISTORY,
                errorCode,
                diagnosticId,
                null,
                null,
                List.of());
    }

    private void validateInvariants() {
        if (stage == PlanningStage.HISTORY) {
            if (authorizationEvidenceRef != null || domainMetadataEvidenceRef != null || !operationAudits.isEmpty()) {
                throw new IllegalArgumentException("HISTORY failure must not carry evidence refs or operation audits");
            }
        }
        if (domainMetadataEvidenceRef != null && authorizationEvidenceRef == null) {
            throw new IllegalArgumentException("domain metadata evidence requires authorization evidence");
        }
        validateAuditOrder(operationAudits);
    }

    static void validateAuditOrder(List<PlanningOperationAudit> audits) {
        if (audits.size() > 2) {
            throw new IllegalArgumentException("operationAudits must contain at most ROUTE and PLAN");
        }
        for (int i = 0; i < audits.size(); i++) {
            RuntimeOperationType expected = i == 0 ? RuntimeOperationType.ROUTE : RuntimeOperationType.PLAN;
            if (audits.get(i).operation() != expected) {
                throw new IllegalArgumentException("operationAudits must be ordered as ROUTE then PLAN");
            }
        }
    }

    static String requireText(String value, String field) {
        Objects.requireNonNull(value, field + " must not be null");
        if (value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
        return value;
    }

    static String normalizeOptionalRef(String value, String field) {
        if (value == null) {
            return null;
        }
        if (value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
        return value;
    }

    static String normalizeOptionalSafeMessage(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        return value.trim();
    }

    public String requestCorrelationId() { return requestCorrelationId; }
    public PlanningStage stage() { return stage; }
    public KernelErrorCode errorCode() { return errorCode; }
    public String diagnosticId() { return diagnosticId; }
    public Optional<String> safeMessage() { return Optional.ofNullable(safeMessage); }
    public Optional<String> authorizationEvidenceRef() { return Optional.ofNullable(authorizationEvidenceRef); }
    public Optional<String> domainMetadataEvidenceRef() { return Optional.ofNullable(domainMetadataEvidenceRef); }
    public List<PlanningOperationAudit> operationAudits() { return operationAudits; }
}
