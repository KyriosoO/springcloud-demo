package com.dylan.agent.planning.model;

import com.dylan.agent.invocation.model.KernelErrorCode;

import java.util.List;
import java.util.Optional;

/**
 * 独立的 Planning 取消值。
 *
 * <p>cancel/deadline 不建模为 PlanningResult 分支，也不伪装成 PlanningFailure。</p>
 */
public final class PlanningCancellation {

    private final String requestCorrelationId;
    private final PlanningStage stage;
    private final KernelErrorCode errorCode;
    private final String authorizationEvidenceRef;
    private final String domainMetadataEvidenceRef;
    private final List<PlanningOperationAudit> operationAudits;

    public PlanningCancellation(String requestCorrelationId,
                                PlanningStage stage,
                                KernelErrorCode errorCode,
                                String authorizationEvidenceRef,
                                String domainMetadataEvidenceRef,
                                List<PlanningOperationAudit> operationAudits) {
        this.requestCorrelationId = PlanningFailure.requireText(requestCorrelationId, "requestCorrelationId");
        this.stage = java.util.Objects.requireNonNull(stage, "stage must not be null");
        this.errorCode = java.util.Objects.requireNonNull(errorCode, "errorCode must not be null");
        this.authorizationEvidenceRef =
                PlanningFailure.normalizeOptionalRef(authorizationEvidenceRef, "authorizationEvidenceRef");
        this.domainMetadataEvidenceRef =
                PlanningFailure.normalizeOptionalRef(domainMetadataEvidenceRef, "domainMetadataEvidenceRef");
        this.operationAudits = List.copyOf(operationAudits == null ? List.of() : operationAudits);
        validateInvariants();
    }

    public static PlanningCancellation beforePlanning(String requestCorrelationId,
                                                      KernelErrorCode errorCode) {
        return new PlanningCancellation(
                requestCorrelationId,
                PlanningStage.HISTORY,
                errorCode,
                null,
                null,
                List.of());
    }

    private void validateInvariants() {
        if (errorCode != KernelErrorCode.CANCELLED && errorCode != KernelErrorCode.DEADLINE_EXCEEDED) {
            throw new IllegalArgumentException("PlanningCancellation only allows CANCELLED or DEADLINE_EXCEEDED");
        }
        if (stage == PlanningStage.HISTORY) {
            if (authorizationEvidenceRef != null || domainMetadataEvidenceRef != null || !operationAudits.isEmpty()) {
                throw new IllegalArgumentException("HISTORY cancellation must not carry evidence refs or audits");
            }
        }
        if (domainMetadataEvidenceRef != null && authorizationEvidenceRef == null) {
            throw new IllegalArgumentException("domain metadata evidence requires authorization evidence");
        }
        PlanningFailure.validateAuditOrder(operationAudits);
    }

    public String requestCorrelationId() { return requestCorrelationId; }
    public PlanningStage stage() { return stage; }
    public KernelErrorCode errorCode() { return errorCode; }
    public Optional<String> authorizationEvidenceRef() { return Optional.ofNullable(authorizationEvidenceRef); }
    public Optional<String> domainMetadataEvidenceRef() { return Optional.ofNullable(domainMetadataEvidenceRef); }
    public List<PlanningOperationAudit> operationAudits() { return operationAudits; }
}
