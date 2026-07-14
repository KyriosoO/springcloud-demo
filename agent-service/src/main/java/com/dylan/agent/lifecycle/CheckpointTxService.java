package com.dylan.agent.lifecycle;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.lifecycle.model.CheckpointResult;
import com.dylan.agent.lifecycle.model.PlanningCheckpoint;
import com.dylan.agent.persistence.entity.AgentInvocationRecordEntity;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Objects;

/**
 * Core 执行前冻结规划检查点的短事务。
 */
@Service
public class CheckpointTxService {

    private final AgentInvocationRecordMapper invocationMapper;
    private final InvocationAuditJsonCodec auditJsonCodec;
    private final Clock clock;

    public CheckpointTxService(AgentInvocationRecordMapper invocationMapper,
                               InvocationAuditJsonCodec auditJsonCodec,
                               Clock clock) {
        this.invocationMapper = Objects.requireNonNull(invocationMapper);
        this.auditJsonCodec = Objects.requireNonNull(auditJsonCodec);
        this.clock = Objects.requireNonNull(clock);
    }

    @Transactional
    public CheckpointResult write(InvocationHandle handle, ExecutablePlanningResult result) {
        PlanningCheckpoint checkpoint = PlanningCheckpoint.from(handle, result);
        String checkpointJson = auditJsonCodec.writeCheckpoint(checkpoint);
        int updated = invocationMapper.checkpoint(
                handle.invocationId(),
                checkpoint.capabilityId(),
                checkpoint.planKind(),
                checkpoint.registrationIdentity(),
                checkpoint.authorizationSnapshotRef(),
                result.artifactIdentity().contextSnapshotSetDigest(),
                result.authorizationSnapshot().domainMetadataEvidence().catalogVersion(),
                checkpoint.planningArtifactBindingDigest(),
                checkpointJson,
                checkpoint.checkpointHash(),
                LocalDateTime.now(clock),
                0,
                0);
        if (updated == 1) {
            return committed(CheckpointResult.Status.COMMITTED, checkpoint);
        }
        AgentInvocationRecordEntity existing = invocationMapper.selectById(handle.invocationId());
        if (existing == null) {
            return CheckpointResult.withoutCheckpoint(CheckpointResult.Status.ROLLBACK_CONFIRMED);
        }
        if (!"PROCESSING".equals(existing.getState())) {
            return CheckpointResult.withoutCheckpoint(CheckpointResult.Status.TERMINAL_EXISTS);
        }
        if (existing.getCheckpointSequence() == 1
                && checkpoint.checkpointHash().equals(existing.getCheckpointHash())
                && checkpoint.planningArtifactBindingDigest()
                        .equals(existing.getPlanningArtifactBindingDigest())) {
            return committed(CheckpointResult.Status.ALREADY_COMMITTED_SAME, checkpoint);
        }
        return CheckpointResult.withoutCheckpoint(CheckpointResult.Status.COMMIT_UNKNOWN);
    }

    private static CheckpointResult committed(
            CheckpointResult.Status status,
            PlanningCheckpoint checkpoint) {
        return CheckpointResult.committed(status, new CheckpointResult.CommittedCheckpoint(
                checkpoint.invocationId(),
                checkpoint.requestCorrelationId(),
                checkpoint.checkpointHash()));
    }
}
