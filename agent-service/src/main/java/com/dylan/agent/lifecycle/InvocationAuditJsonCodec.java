package com.dylan.agent.lifecycle;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.common.RuntimeTerminationReason;
import com.dylan.agent.lifecycle.model.PlanningCheckpoint;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.dylan.agent.planning.model.RuntimeMetadataStatus;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Objects;

/**
 * 仅用于生命周期审计值的 JSON 编解码器。
 */
@Component
public class InvocationAuditJsonCodec {

    private final ObjectMapper objectMapper;

    public InvocationAuditJsonCodec(ObjectMapper objectMapper) {
        this.objectMapper = Objects.requireNonNull(objectMapper).copy();
    }

    public String writeCheckpoint(PlanningCheckpoint checkpoint) {
        Objects.requireNonNull(checkpoint, "checkpoint must not be null");
        try {
            return objectMapper.writeValueAsString(PlanningCheckpointAuditDto.from(checkpoint));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("serialize planning checkpoint failed", ex);
        }
    }

    private record PlanningCheckpointAuditDto(
            String invocationId,
            String requestCorrelationId,
            String capabilityId,
            String domain,
            String planKind,
            String registrationIdentity,
            PlanningOperationAuditDto routeAudit,
            PlanningOperationAuditDto planAudit,
            String authorizationSnapshotRef,
            List<ContextSnapshotRefDto> contextSnapshotRefs,
            String checkpointHash) {

        private static PlanningCheckpointAuditDto from(PlanningCheckpoint checkpoint) {
            return new PlanningCheckpointAuditDto(
                    checkpoint.invocationId(),
                    checkpoint.requestCorrelationId(),
                    checkpoint.capabilityId(),
                    checkpoint.domain(),
                    checkpoint.planKind(),
                    checkpoint.registrationIdentity(),
                    PlanningOperationAuditDto.from(checkpoint.routeAudit()),
                    PlanningOperationAuditDto.from(checkpoint.planAudit()),
                    checkpoint.authorizationSnapshotRef(),
                    checkpoint.contextSnapshotRefs().stream()
                            .map(ContextSnapshotRefDto::from)
                            .toList(),
                    checkpoint.checkpointHash());
        }
    }

    private record PlanningOperationAuditDto(
            RuntimeOperationType operation,
            RuntimeMetadataStatus metadataStatus,
            RuntimeMetadataDto runtimeMetadata,
            long localDurationMs,
            PlanningOperationTermination termination) {

        private static PlanningOperationAuditDto from(
                com.dylan.agent.planning.model.PlanningOperationAudit audit) {
            return new PlanningOperationAuditDto(
                    audit.operation(),
                    audit.metadataStatus(),
                    audit.runtimeMetadata().map(RuntimeMetadataDto::from).orElse(null),
                    audit.localDurationMs(),
                    audit.termination());
        }
    }

    private record RuntimeMetadataDto(
            RuntimeOperationType operation,
            Integer providerAttempts,
            Integer repairAttempts,
            Long repairDurationMs,
            Long totalDurationMs,
            RuntimeTerminationReason terminationReason,
            Boolean deadlineReached,
            Boolean repairLimitReached) {

        private static RuntimeMetadataDto from(RuntimeOperationMetadata metadata) {
            return new RuntimeMetadataDto(
                    metadata.getOperation(),
                    metadata.getProviderAttempts(),
                    metadata.getRepairAttempts(),
                    metadata.getRepairDurationMs(),
                    metadata.getTotalDurationMs(),
                    metadata.getTerminationReason(),
                    metadata.getDeadlineReached(),
                    metadata.getRepairLimitReached());
        }
    }

    private record ContextSnapshotRefDto(
            String contextId,
            RuntimeContextType contextType,
            String sourceDomain,
            ContractRefDto storedContractRef,
            ContractRefDto effectiveContractRef,
            long recordVersion) {

        private static ContextSnapshotRefDto from(PlanningCheckpoint.ContextSnapshotRef ref) {
            return new ContextSnapshotRefDto(
                    ref.contextId(),
                    ref.contextType(),
                    ref.sourceDomain().orElse(null),
                    ContractRefDto.from(ref.storedContractRef()),
                    ContractRefDto.from(ref.effectiveContractRef()),
                    ref.recordVersion());
        }
    }

    private record ContractRefDto(String schema, String version) {
        private static ContractRefDto from(ContractRef ref) {
            return new ContractRefDto(ref.schema(), ref.version());
        }
    }
}
