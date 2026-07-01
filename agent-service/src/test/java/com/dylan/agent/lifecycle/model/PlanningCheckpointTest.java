package com.dylan.agent.lifecycle.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class PlanningCheckpointTest {

    @Test
    void checkpointResultExposesCommittedCheckpointAsOptional() {
        CheckpointResult.CommittedCheckpoint committed =
                new CheckpointResult.CommittedCheckpoint("inv-1", "corr-1", "hash-1");

        assertThat(CheckpointResult.committed(CheckpointResult.Status.COMMITTED, committed).committed())
                .contains(committed);
        assertThat(CheckpointResult.withoutCheckpoint(CheckpointResult.Status.COMMIT_UNKNOWN).committed())
                .isEmpty();
        assertThatThrownBy(() -> CheckpointResult.withoutCheckpoint(CheckpointResult.Status.COMMITTED))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void contextSnapshotRefsAreSortedAndImmutable() {
        PlanningCheckpoint checkpoint = baseBuilder()
                .contextSnapshotRefs(List.of(
                        ref("ctx-aggregate", RuntimeContextType.AGGREGATE, 2),
                        ref("ctx-query", RuntimeContextType.QUERY, 1)))
                .build();

        assertThat(checkpoint.contextSnapshotRefs())
                .extracting(PlanningCheckpoint.ContextSnapshotRef::contextType)
                .containsExactly(RuntimeContextType.AGGREGATE, RuntimeContextType.QUERY);
        assertThatThrownBy(() -> checkpoint.contextSnapshotRefs().add(
                ref("ctx-other", RuntimeContextType.QUERY, 3)))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void contextSnapshotRefsRejectDuplicateTypeOrInvalidValues() {
        assertThatThrownBy(() -> baseBuilder()
                .contextSnapshotRefs(List.of(
                        ref("ctx-1", RuntimeContextType.QUERY, 1),
                        ref("ctx-2", RuntimeContextType.QUERY, 2)))
                .build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("duplicate contextType");

        assertThatThrownBy(() -> new PlanningCheckpoint.ContextSnapshotRef(
                "ctx-1",
                RuntimeContextType.QUERY,
                Optional.of(" "),
                contract(),
                contract(),
                1))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("sourceDomain");
    }

    @Test
    void checkpointHashIncludesContextSnapshotRefs() {
        PlanningCheckpoint v1 = baseBuilder()
                .contextSnapshotRefs(List.of(ref("ctx-query", RuntimeContextType.QUERY, 1)))
                .build();
        PlanningCheckpoint v2 = baseBuilder()
                .contextSnapshotRefs(List.of(ref("ctx-query", RuntimeContextType.QUERY, 2)))
                .build();

        assertThat(v1.checkpointHash()).isNotEqualTo(v2.checkpointHash());
    }

    @Test
    void checkpointHashIncludesOperationAudits() {
        PlanningCheckpoint v1 = baseBuilder()
                .routeAudit(audit(RuntimeOperationType.ROUTE, 1L))
                .build();
        PlanningCheckpoint v2 = baseBuilder()
                .routeAudit(audit(RuntimeOperationType.ROUTE, 2L))
                .build();

        assertThat(v1.checkpointHash()).isNotEqualTo(v2.checkpointHash());
    }

    @Test
    void checkpointRequiresStableIdentityFields() {
        assertThatThrownBy(() -> baseBuilder().capabilityId(" ").build())
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("capabilityId");

        assertThatThrownBy(() -> baseBuilder().registrationIdentity(null).build())
                .isInstanceOf(NullPointerException.class)
                .hasMessageContaining("registrationIdentity");
    }

    private PlanningCheckpoint.Builder baseBuilder() {
        return new PlanningCheckpoint.Builder()
                .invocationId("inv-1")
                .requestCorrelationId("corr-1")
                .capabilityId("query.search")
                .domain("employee")
                .planKind("QUERY")
                .registrationIdentity("registration-v1")
                .routeAudit(audit(RuntimeOperationType.ROUTE))
                .planAudit(audit(RuntimeOperationType.PLAN))
                .authorizationSnapshotRef("auth-snapshot-1");
    }

    private PlanningCheckpoint.ContextSnapshotRef ref(
            String contextId,
            RuntimeContextType contextType,
            long version) {
        return new PlanningCheckpoint.ContextSnapshotRef(
                contextId,
                contextType,
                Optional.of("employee"),
                contract(),
                contract(),
                version);
    }

    private ContractRef contract() {
        return new ContractRef("agent_context", "v1");
    }

    private PlanningOperationAudit audit(RuntimeOperationType operation) {
        return audit(operation, 1L);
    }

    private PlanningOperationAudit audit(RuntimeOperationType operation, long localDurationMs) {
        RuntimeOperationMetadata metadata = new RuntimeOperationMetadata();
        metadata.setOperation(operation);
        metadata.setProviderAttempts(1);
        metadata.setRepairAttempts(0);
        metadata.setRepairDurationMs(0L);
        metadata.setTotalDurationMs(1L);
        metadata.setTerminationReason(RuntimeTerminationReason.COMPLETED);
        metadata.setDeadlineReached(false);
        metadata.setRepairLimitReached(false);
        return PlanningOperationAudit.reported(metadata, localDurationMs, PlanningOperationTermination.OUTCOME_RECEIVED);
    }
}
