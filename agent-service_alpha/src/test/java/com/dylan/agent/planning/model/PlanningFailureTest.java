package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.invocation.model.KernelErrorCode;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PlanningFailureTest {

    @Test
    void historyProjectionAllowsOnlyPersistenceOrInternalFailureWithoutEvidence() {
        PlanningFailure persistence = PlanningFailure.historyProjection(
                "corr-1",
                KernelErrorCode.PERSISTENCE_FAILED,
                "diag-1");

        assertThat(persistence.stage()).isEqualTo(PlanningStage.HISTORY);
        assertThat(persistence.authorizationEvidenceRef()).isEmpty();
        assertThat(persistence.domainMetadataEvidenceRef()).isEmpty();
        assertThat(persistence.operationAudits()).isEmpty();

        assertThatThrownBy(() -> PlanningFailure.historyProjection(
                "corr-1",
                KernelErrorCode.PERMISSION_UNAVAILABLE,
                "diag-1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("history projection only allows");
    }

    @Test
    void historyFailureRejectsEvidenceAndAudits() {
        assertThatThrownBy(() -> new PlanningFailure(
                "corr-1",
                PlanningStage.HISTORY,
                KernelErrorCode.INTERNAL_ERROR,
                "diag-1",
                "auth-evidence",
                null,
                List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("HISTORY failure");
    }

    @Test
    void domainMetadataEvidenceRequiresAuthorizationEvidence() {
        assertThatThrownBy(() -> new PlanningFailure(
                "corr-1",
                PlanningStage.PLAN,
                KernelErrorCode.DOMAIN_BINDING_UNAVAILABLE,
                "diag-1",
                null,
                "domain-evidence",
                List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("requires authorization evidence");
    }

    @Test
    void operationAuditsMustBeRouteThenPlan() {
        PlanningOperationAudit route = PlanningOperationAudit.notReported(
                RuntimeOperationType.ROUTE,
                10,
                PlanningOperationTermination.DEADLINE_EXCEEDED);
        PlanningOperationAudit plan = PlanningOperationAudit.notReported(
                RuntimeOperationType.PLAN,
                20,
                PlanningOperationTermination.DEADLINE_EXCEEDED);

        PlanningFailure failure = new PlanningFailure(
                "corr-1",
                PlanningStage.PLAN,
                KernelErrorCode.RUNTIME_UNAVAILABLE,
                "diag-1",
                "auth-evidence",
                "domain-evidence",
                List.of(route, plan));

        assertThat(failure.operationAudits()).containsExactly(route, plan);

        assertThatThrownBy(() -> new PlanningFailure(
                "corr-1",
                PlanningStage.PLAN,
                KernelErrorCode.RUNTIME_UNAVAILABLE,
                "diag-1",
                "auth-evidence",
                "domain-evidence",
                List.of(plan, route)))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("ROUTE then PLAN");
    }

    @Test
    void planningCancellationIsSeparateTypedChannel() {
        PlanningCancellation cancellation = PlanningCancellation.beforePlanning(
                "corr-1",
                KernelErrorCode.CANCELLED);

        assertThat(cancellation.stage()).isEqualTo(PlanningStage.HISTORY);
        assertThat(cancellation.errorCode()).isEqualTo(KernelErrorCode.CANCELLED);
        assertThat(cancellation.operationAudits()).isEmpty();

        PlanningCancellationException exception = new PlanningCancellationException(cancellation);
        assertThat(exception.getMessage()).isEqualTo("CANCELLED");
        assertThat(exception.cancellation()).isSameAs(cancellation);
    }

    @Test
    void planningCancellationAllowsOnlyCancellationCodesAndHistoryHasNoEvidence() {
        assertThatThrownBy(() -> PlanningCancellation.beforePlanning(
                "corr-1",
                KernelErrorCode.INTERNAL_ERROR))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("only allows CANCELLED or DEADLINE_EXCEEDED");

        assertThatThrownBy(() -> new PlanningCancellation(
                "corr-1",
                PlanningStage.HISTORY,
                KernelErrorCode.DEADLINE_EXCEEDED,
                "auth-evidence",
                null,
                List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("HISTORY cancellation");
    }
}
