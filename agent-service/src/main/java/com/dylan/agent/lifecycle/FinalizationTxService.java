package com.dylan.agent.lifecycle;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.response.AgentResultPayload;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationState;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.core.ExecutionFailure;
import com.dylan.agent.kernel.core.ExecutionSuccess;
import com.dylan.agent.kernel.definition.ContractRegistry;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.lifecycle.model.CheckpointResult;
import com.dylan.agent.lifecycle.model.FinalizedInvocationResult;
import com.dylan.agent.lifecycle.model.InvocationResponseType;
import com.dylan.agent.lifecycle.model.StoredInvocationResult;
import com.dylan.agent.lifecycle.port.ContextFinalizationParticipant;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.persistence.entity.AgentInvocationResultEntity;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentInvocationResultMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.dylan.agent.planning.model.PlanningCancellation;
import com.dylan.agent.planning.model.PlanningFailure;
import com.dylan.agent.planning.model.ResolvedClarification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Objects;
import java.util.UUID;

/**
 * 所有终态调用状态的终结事务边界。
 */
@Service
public class FinalizationTxService {

    private final AgentInvocationRecordMapper invocationMapper;
    private final AgentInvocationResultMapper resultMapper;
    private final AgentTurnMapper turnMapper;
    private final ContextFinalizationParticipant contextFinalizationParticipant;
    private final PayloadJsonCodec payloadJsonCodec;
    private final ContractRegistry contractRegistry;
    private final Clock clock;

    public FinalizationTxService(AgentInvocationRecordMapper invocationMapper,
                                 AgentInvocationResultMapper resultMapper,
                                 AgentTurnMapper turnMapper,
                                 ContextFinalizationParticipant contextFinalizationParticipant,
                                 PayloadJsonCodec payloadJsonCodec,
                                 ContractRegistry contractRegistry,
                                 Clock clock) {
        this.invocationMapper = Objects.requireNonNull(invocationMapper);
        this.resultMapper = Objects.requireNonNull(resultMapper);
        this.turnMapper = Objects.requireNonNull(turnMapper);
        this.contextFinalizationParticipant = Objects.requireNonNull(contextFinalizationParticipant);
        this.payloadJsonCodec = Objects.requireNonNull(payloadJsonCodec);
        this.contractRegistry = Objects.requireNonNull(contractRegistry);
        this.clock = Objects.requireNonNull(clock);
    }

    @Transactional
    public FinalizedInvocationResult commitSuccess(
            InvocationHandle handle,
            CheckpointResult checkpoint,
            ExecutionSuccess success) {
        Objects.requireNonNull(checkpoint).requireCommittedCheckpoint();
        Objects.requireNonNull(success, "success must not be null");
        StoredInvocationResult stored = storeResult(handle, success.securedResult());
        contextFinalizationParticipant.persist(success.approvedContextWrites());
        finalizeInvocation(handle, InvocationState.COMPLETED, InvocationResponseType.SUCCESS,
                null, stored.safeMessage(), null);
        finalizeTurnSuccess(handle, InvocationResponseType.SUCCESS, stored.safeMessage());
        return finalized(handle, InvocationState.COMPLETED, InvocationResponseType.SUCCESS,
                stored, stored.safeMessage(), null, null);
    }

    @Transactional
    public FinalizedInvocationResult commitClarification(
            InvocationHandle handle,
            ResolvedClarification clarification) {
        Objects.requireNonNull(clarification, "clarification must not be null");
        finalizeInvocation(handle, InvocationState.COMPLETED, InvocationResponseType.CLARIFY,
                null, clarification.safeQuestion(), null);
        finalizeTurnSuccess(handle, InvocationResponseType.CLARIFY, clarification.safeQuestion());
        return finalized(handle, InvocationState.COMPLETED, InvocationResponseType.CLARIFY,
                null, clarification.safeQuestion(), null, null);
    }

    @Transactional
    public FinalizedInvocationResult commitPlanningFailure(
            InvocationHandle handle,
            PlanningFailure failure) {
        Objects.requireNonNull(failure, "failure must not be null");
        String safeMessage = "规划失败，请稍后重试。";
        finalizeInvocation(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                failure.errorCode(), safeMessage, failure.diagnosticId());
        finalizeTurnFailure(handle, failure.errorCode(), safeMessage);
        return finalized(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                null, safeMessage, failure.errorCode(), failure.diagnosticId());
    }

    @Transactional
    public FinalizedInvocationResult commitPlanningCancellation(
            InvocationHandle handle,
            PlanningCancellation cancellation) {
        Objects.requireNonNull(cancellation, "cancellation must not be null");
        return commitCancellation(handle, cancellation.errorCode(), "请求已取消或超时。", null);
    }

    @Transactional
    public FinalizedInvocationResult commitExecutionFailure(
            InvocationHandle handle,
            CheckpointResult checkpoint,
            ExecutionFailure failure) {
        Objects.requireNonNull(checkpoint).requireCommittedCheckpoint();
        Objects.requireNonNull(failure, "failure must not be null");
        if (failure.cancelled()) {
            return commitExecutionCancelled(handle, checkpoint, failure);
        }
        String safeMessage = "执行失败，请稍后重试。";
        finalizeInvocation(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                failure.errorCode(), safeMessage, failure.diagnosticId());
        finalizeTurnFailure(handle, failure.errorCode(), safeMessage);
        return finalized(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                null, safeMessage, failure.errorCode(), failure.diagnosticId());
    }

    @Transactional
    public FinalizedInvocationResult commitExecutionCancelled(
            InvocationHandle handle,
            CheckpointResult checkpoint,
            ExecutionFailure failure) {
        Objects.requireNonNull(checkpoint).requireCommittedCheckpoint();
        Objects.requireNonNull(failure, "failure must not be null");
        return commitCancellation(handle, failure.errorCode(), "请求已取消或超时。", failure.diagnosticId());
    }

    private FinalizedInvocationResult commitCancellation(
            InvocationHandle handle,
            KernelErrorCode errorCode,
            String safeMessage,
            String diagnosticId) {
        finalizeInvocation(handle, InvocationState.CANCELLED, InvocationResponseType.CANCELLED,
                errorCode, safeMessage, diagnosticId);
        finalizeTurnFailure(handle, errorCode, safeMessage);
        return finalized(handle, InvocationState.CANCELLED, InvocationResponseType.CANCELLED,
                null, safeMessage, errorCode, diagnosticId);
    }

    private StoredInvocationResult storeResult(InvocationHandle handle, SecuredResult secured) {
        ContractRef ref = secured.outputContract();
        Class<?> javaType = contractRegistry.require(ref).javaType();
        Object payload = payloadJsonCodec.deserialize(secured.canonicalPayload(), javaType);
        if (!(payload instanceof AgentResultPayload resultPayload)) {
            throw new IllegalStateException("output contract is not an AgentResultPayload: " + ref);
        }
        AgentInvocationResultEntity entity = new AgentInvocationResultEntity();
        entity.setId(UUID.randomUUID().toString());
        entity.setInvocationId(handle.invocationId());
        entity.setOutputContractSchema(ref.schema());
        entity.setOutputContractVersion(ref.version());
        entity.setPayloadJson(new String(secured.canonicalPayload(), StandardCharsets.UTF_8));
        entity.setSafeMessage(secured.safeMessage());
        entity.setSafeSummary(secured.safeSummary());
        entity.setCreatedAt(LocalDateTime.now(clock));
        if (resultMapper.insert(entity) != 1) {
            throw new IllegalStateException("store invocation result failed");
        }
        return new StoredInvocationResult(
                entity.getId(),
                ref,
                resultPayload,
                secured.safeMessage(),
                secured.safeSummary());
    }

    private void finalizeInvocation(InvocationHandle handle,
                                    InvocationState state,
                                    InvocationResponseType responseType,
                                    KernelErrorCode errorCode,
                                    String safeMessage,
                                    String diagnosticId) {
        int updated = invocationMapper.finalizeTerminal(
                handle.invocationId(),
                state.name(),
                responseType.name(),
                errorCode == null ? null : errorCode.name(),
                safeMessage,
                diagnosticId,
                LocalDateTime.now(clock));
        if (updated != 1) {
            throw new IllegalStateException("finalize invocation CAS failed: " + handle.invocationId());
        }
    }

    private void finalizeTurnSuccess(
            InvocationHandle handle,
            InvocationResponseType responseType,
            String safeMessage) {
        ChatInvocationOrigin origin = chatOrigin(handle);
        int updated = turnMapper.finalizeSuccess(
                origin.turnId(),
                handle.invocationId(),
                responseType.name(),
                safeMessage,
                LocalDateTime.now(clock));
        if (updated != 1) {
            throw new IllegalStateException("finalize turn success CAS failed: " + origin.turnId());
        }
    }

    private void finalizeTurnFailure(
            InvocationHandle handle,
            KernelErrorCode errorCode,
            String safeMessage) {
        ChatInvocationOrigin origin = chatOrigin(handle);
        int updated = turnMapper.finalizeFailure(
                origin.turnId(),
                handle.invocationId(),
                errorCode.name(),
                safeMessage,
                LocalDateTime.now(clock));
        if (updated != 1) {
            throw new IllegalStateException("finalize turn failure CAS failed: " + origin.turnId());
        }
    }

    private static ChatInvocationOrigin chatOrigin(InvocationHandle handle) {
        if (handle.origin() instanceof ChatInvocationOrigin origin) {
            return origin;
        }
        throw new IllegalArgumentException("D03 finalization only supports CHAT origin");
    }

    private static FinalizedInvocationResult finalized(
            InvocationHandle handle,
            InvocationState state,
            InvocationResponseType responseType,
            StoredInvocationResult stored,
            String safeMessage,
            KernelErrorCode errorCode,
            String diagnosticId) {
        return FinalizedInvocationResult.builder()
                .invocationId(handle.invocationId())
                .origin(handle.origin())
                .state(state)
                .responseType(responseType)
                .storedResult(stored)
                .safeMessage(safeMessage)
                .errorCode(errorCode)
                .diagnosticId(diagnosticId)
                .build();
    }
}
