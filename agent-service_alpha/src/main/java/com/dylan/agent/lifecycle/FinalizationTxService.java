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
import com.dylan.agent.persistence.entity.AgentInvocationRecordEntity;
import com.dylan.agent.persistence.mapper.AgentInvocationRecordMapper;
import com.dylan.agent.persistence.mapper.AgentInvocationResultMapper;
import com.dylan.agent.persistence.mapper.AgentTurnMapper;
import com.dylan.agent.planning.model.PlanningCancellation;
import com.dylan.agent.planning.model.PlanningFailure;
import com.dylan.agent.planning.model.ResolvedClarification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.LocalDateTime;
import java.util.Objects;
import java.util.Optional;
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
        if (!tryFinalizeInvocation(handle, InvocationState.COMPLETED, InvocationResponseType.SUCCESS,
                null, success.securedResult().safeMessage(), null, 1)) {
            return requireAuthoritativeTerminal(handle);
        }
        StoredInvocationResult stored = storeResult(handle, success.securedResult());
        contextFinalizationParticipant.persist(success.approvedContextWrites());
        finalizeTurnSuccess(handle, InvocationResponseType.SUCCESS, stored.safeMessage());
        return finalized(handle, InvocationState.COMPLETED, InvocationResponseType.SUCCESS,
                stored, stored.safeMessage(), null, null);
    }

    @Transactional
    public FinalizedInvocationResult commitClarification(
            InvocationHandle handle,
            ResolvedClarification clarification) {
        Objects.requireNonNull(clarification, "clarification must not be null");
        if (!tryFinalizeInvocation(handle, InvocationState.COMPLETED, InvocationResponseType.CLARIFY,
                null, clarification.safeQuestion(), null, 0)) {
            return requireAuthoritativeTerminal(handle);
        }
        finalizeTurnSuccess(handle, InvocationResponseType.CLARIFY, clarification.safeQuestion());
        return finalized(handle, InvocationState.COMPLETED, InvocationResponseType.CLARIFY,
                null, clarification.safeQuestion(), null, null);
    }

    @Transactional
    public FinalizedInvocationResult commitPlanningFailure(
            InvocationHandle handle,
            PlanningFailure failure) {
        Objects.requireNonNull(failure, "failure must not be null");
        String safeMessage = failure.safeMessage().orElse("规划失败，请稍后重试。");
        if (!tryFinalizeInvocation(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                failure.errorCode(), safeMessage, failure.diagnosticId(), 0)) {
            return requireAuthoritativeTerminal(handle);
        }
        finalizeTurnFailure(handle, failure.errorCode(), safeMessage);
        return finalized(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                null, safeMessage, failure.errorCode(), failure.diagnosticId());
    }

    @Transactional
    public FinalizedInvocationResult commitPlanningCancellation(
            InvocationHandle handle,
            PlanningCancellation cancellation) {
        Objects.requireNonNull(cancellation, "cancellation must not be null");
        return commitCancellation(handle, cancellation.errorCode(), "请求已取消或超时。", null, 0);
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
        String safeMessage = failure.safeMessage() == null
                ? "执行失败，请稍后重试。"
                : failure.safeMessage();
        if (!tryFinalizeInvocation(handle, InvocationState.FAILED, InvocationResponseType.FAILURE,
                failure.errorCode(), safeMessage, failure.diagnosticId(), 1)) {
            return requireAuthoritativeTerminal(handle);
        }
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
        return commitCancellation(handle, failure.errorCode(), "请求已取消或超时。", failure.diagnosticId(), 1);
    }

    private FinalizedInvocationResult commitCancellation(
            InvocationHandle handle,
            KernelErrorCode errorCode,
            String safeMessage,
            String diagnosticId,
            long expectedRowVersion) {
        if (!tryFinalizeInvocation(handle, InvocationState.CANCELLED, InvocationResponseType.CANCELLED,
                errorCode, safeMessage, diagnosticId, expectedRowVersion)) {
            return requireAuthoritativeTerminal(handle);
        }
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
        entity.setOutputContractNamespace(ref.namespace());
        entity.setOutputContractName(ref.name());
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

    private boolean tryFinalizeInvocation(InvocationHandle handle,
                                          InvocationState state,
                                          InvocationResponseType responseType,
                                          KernelErrorCode errorCode,
                                          String safeMessage,
                                          String diagnosticId,
                                          long expectedRowVersion) {
        int updated = invocationMapper.finalizeTerminal(
                handle.invocationId(),
                state.name(),
                responseType.name(),
                errorCode == null ? null : errorCode.name(),
                safeMessage,
                diagnosticId,
                LocalDateTime.now(clock),
                expectedRowVersion);
        return updated == 1;
    }

    /**
     * 在独立事务中重读已提交的权威终态，供提交结果未知时由 Lifecycle 对账。
     */
    @Transactional(readOnly = true, propagation = Propagation.REQUIRES_NEW)
    public Optional<FinalizedInvocationResult> readAuthoritativeTerminal(InvocationHandle handle) {
        Objects.requireNonNull(handle, "handle must not be null");
        return loadAuthoritativeTerminal(handle);
    }

    private FinalizedInvocationResult requireAuthoritativeTerminal(InvocationHandle handle) {
        return loadAuthoritativeTerminal(handle).orElseThrow(() ->
                new IllegalStateException(
                        "finalize invocation CAS failed without authoritative terminal: "
                                + handle.invocationId()));
    }

    private Optional<FinalizedInvocationResult> loadAuthoritativeTerminal(InvocationHandle handle) {
        AgentInvocationRecordEntity record = invocationMapper.selectById(handle.invocationId());
        if (record == null || InvocationState.PROCESSING.name().equals(record.getState())) {
            return Optional.empty();
        }
        validateAuthoritativeBinding(handle, record);
        InvocationState state = enumValue(InvocationState.class, record.getState(), "state");
        InvocationResponseType responseType = enumValue(
                InvocationResponseType.class, record.getResponseType(), "responseType");
        StoredInvocationResult stored = responseType == InvocationResponseType.SUCCESS
                ? loadStoredResult(handle.invocationId())
                : null;
        KernelErrorCode errorCode = record.getErrorCode() == null
                ? null
                : enumValue(KernelErrorCode.class, record.getErrorCode(), "errorCode");
        return Optional.of(finalized(
                handle,
                state,
                responseType,
                stored,
                requireNonBlank(record.getSafeMessage(), "safeMessage"),
                errorCode,
                record.getDiagnosticId()));
    }

    private StoredInvocationResult loadStoredResult(String invocationId) {
        AgentInvocationResultEntity entity = resultMapper.selectByInvocationId(invocationId);
        if (entity == null) {
            throw new IllegalStateException(
                    "authoritative SUCCESS invocation has no stored result: " + invocationId);
        }
        ContractRef ref = new ContractRef(
                entity.getOutputContractNamespace(),
                entity.getOutputContractName(),
                entity.getOutputContractVersion());
        Class<?> javaType = contractRegistry.require(ref).javaType();
        Object payload = payloadJsonCodec.deserialize(
                entity.getPayloadJson().getBytes(StandardCharsets.UTF_8), javaType);
        if (!(payload instanceof AgentResultPayload resultPayload)) {
            throw new IllegalStateException("output contract is not an AgentResultPayload: " + ref);
        }
        return new StoredInvocationResult(
                entity.getId(), ref, resultPayload, entity.getSafeMessage(), entity.getSafeSummary());
    }

    private static void validateAuthoritativeBinding(
            InvocationHandle handle,
            AgentInvocationRecordEntity record) {
        ChatInvocationOrigin origin = chatOrigin(handle);
        if (!handle.requestCorrelationId().equals(record.getRequestCorrelationId())
                || !origin.conversationId().equals(record.getConversationId())
                || !origin.turnId().equals(record.getTurnId())) {
            throw new IllegalStateException(
                    "authoritative invocation binding mismatch: " + handle.invocationId());
        }
    }

    private static <E extends Enum<E>> E enumValue(
            Class<E> type,
            String value,
            String field) {
        try {
            return Enum.valueOf(type, requireNonBlank(value, field));
        } catch (IllegalArgumentException ex) {
            throw new IllegalStateException("invalid authoritative " + field + ": " + value, ex);
        }
    }

    private static String requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("authoritative " + field + " must not be blank");
        }
        return value;
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
