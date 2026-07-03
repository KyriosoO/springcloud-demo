package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.HandlerCandidate;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.AuthorizationExecutionPort;
import com.dylan.agent.kernel.port.ContextApprovalPort;
import com.dylan.agent.kernel.port.ContextExecutionPort;
import com.dylan.agent.kernel.port.DomainExecutionPort;
import com.dylan.agent.kernel.port.ResultSecurityPort;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.kernel.port.model.DomainBindingRequest;
import com.dylan.agent.kernel.port.model.DomainExecutionResolution;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.kernel.port.model.SecuredResult;
import com.dylan.agent.invocation.model.ExecutionStage;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.time.Clock;
import java.util.List;
import java.util.Objects;
import java.util.UUID;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * 所有 capability 共享的可信执行算法，由 D02_01 唯一负责。
 *
 * <p>不按 capabilityId/domain/planKind 分支。不持久化、不调用 Runtime、不重新查询 Registry。
 */
public final class ExecutionCore {

    private static final Logger log = LoggerFactory.getLogger(ExecutionCore.class);

    private final AuthorizationExecutionPort authPort;
    private final ContextExecutionPort contextPort;
    private final DomainExecutionPort domainPort;
    private final ContextApprovalPort contextApprovalPort;
    private final ResultSecurityPort resultSecurityPort;
    private final Clock clock;

    public ExecutionCore(AuthorizationExecutionPort authPort,
                         ContextExecutionPort contextPort,
                         DomainExecutionPort domainPort,
                         ContextApprovalPort contextApprovalPort,
                         ResultSecurityPort resultSecurityPort,
                         Clock clock) {
        this.authPort = Objects.requireNonNull(authPort);
        this.contextPort = Objects.requireNonNull(contextPort);
        this.domainPort = Objects.requireNonNull(domainPort);
        this.contextApprovalPort = Objects.requireNonNull(contextApprovalPort);
        this.resultSecurityPort = Objects.requireNonNull(resultSecurityPort);
        this.clock = Objects.requireNonNull(clock);
    }

    /**
     * 13 步可信执行算法。步骤不可跳过。任何失败都不调用后续阶段。
     *
     * <p>D02_01 阶段 port 实现尚未就绪，Core 算法骨架就绪后由 D03 完成集成。
     */
    public ExecutionOutcome execute(ExecutionCommand command) {
        Objects.requireNonNull(command);

        if (command.handle().isExpired(clock)) {
            return failure(ExecutionStage.EXECUTION_PREFLIGHT, KernelErrorCode.DEADLINE_EXCEEDED, true);
        }

        ResolvedRegistration resolved;
        try {
            resolved = validateRegistrationIdentity(command);
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.EXECUTION_PREFLIGHT, KernelErrorCode.REGISTRATION_MISMATCH, false);
        }

        CapabilityRegistration<?, ?, ?> reg = resolved.registration();
        try {
            validateBinding(command, reg);
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.EXECUTION_PREFLIGHT, KernelErrorCode.REGISTRATION_MISMATCH, false);
        }

        ExecutionScope execScope;
        try {
            execScope = authPort.recheck(command.planningResult().authorizationSnapshot(), command.handle());
            if (!execScope.allowedCapabilityIds().contains(reg.definition().capabilityId())) {
                return failure(ExecutionStage.AUTHORIZATION, KernelErrorCode.AUTHORIZATION_REVOKED, false);
            }
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.AUTHORIZATION, KernelErrorCode.AUTHORIZATION_REVOKED, false);
        }

        try {
            contextPort.revalidateAll(command.planningResult().contextSnapshots(),
                    command.handle(), resolved, execScope);
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.CONTEXT_VALIDATION, KernelErrorCode.CONTEXT_STALE, false);
        }

        DomainResolution domainResolution;
        try {
            domainResolution = resolveBinding(command, resolved, reg, execScope);
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.BINDING, KernelErrorCode.DOMAIN_BINDING_UNAVAILABLE, false);
        }

        ExecutionValidationContext valCtx = buildValidationContext(
                command, reg, domainResolution.projection(), execScope, domainResolution.binding());

        if (command.handle().isExpired(clock)) {
            return failure(ExecutionStage.CANCELLATION_DEADLINE, KernelErrorCode.DEADLINE_EXCEEDED, true);
        }

        var handle = validatePlan(command, reg, valCtx);
        if (handle == null) {
            return failure(ExecutionStage.PLAN_VALIDATION, KernelErrorCode.PLAN_VALIDATION_FAILED, false);
        }

        ExecutionContext execCtx = buildExecutionContext(command, domainResolution.binding());

        if (command.handle().isExpired(clock)) {
            return failure(ExecutionStage.CANCELLATION_DEADLINE, KernelErrorCode.DEADLINE_EXCEEDED, true);
        }

        HandlerCandidate candidate;
        try {
            candidate = reg.executeValidated(handle, execCtx);
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.HANDLER, KernelErrorCode.HANDLER_FAILED, false);
        }

        if (command.handle().isExpired(clock)) {
            return failure(ExecutionStage.CANCELLATION_DEADLINE, KernelErrorCode.DEADLINE_EXCEEDED, true);
        }

        try {
            reg.validateOutput(candidate.output());
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.OUTPUT_VALIDATION, KernelErrorCode.OUTPUT_INVALID, false);
        }

        SecuredResult secured;
        try {
            secured = resultSecurityPort.secure(
                    candidate.output(), reg.definition().outputContract(), execScope);
            validateSecuredResult(secured, reg);
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.RESULT_SECURITY, KernelErrorCode.RESULT_SECURITY_FAILED, false);
        }

        List<ApprovedContextWrite> approvedWrites;
        try {
            approvedWrites = contextApprovalPort.approve(candidate.contextWrites(),
                    new ContextApprovalRequest(command.handle(), resolved, execScope,
                            command.planningResult().contextSnapshots(),
                            command.planningResult().domain().orElse(null),
                            clock.instant()));
            Objects.requireNonNull(approvedWrites, "approved context writes must not be null");
        } catch (RuntimeException ex) {
            return failure(ExecutionStage.CONTEXT_APPROVAL, KernelErrorCode.CONTEXT_WRITE_CONFLICT, false);
        }

        return new ExecutionSuccess(secured, approvedWrites,
                reg.definition().capabilityId(), reg.definition().planKind());
    }

    private ResolvedRegistration validateRegistrationIdentity(ExecutionCommand cmd) {
        var r = cmd.planningResult().resolvedRegistration();
        r.validateIdentity();
        return r;
    }

    private void validateBinding(ExecutionCommand cmd, CapabilityRegistration<?, ?, ?> reg) {
        var raw = cmd.planningResult().rawPlan();
        if (!reg.rawPlanType().isInstance(raw)) {
            throw new IllegalStateException("raw plan subtype mismatch");
        }
        if (!cmd.planningResult().capabilityId().equals(reg.definition().capabilityId())
                || cmd.planningResult().planKind() != reg.definition().planKind()) {
            throw new IllegalStateException("planning result/registration binding mismatch");
        }
    }

    private DomainResolution resolveBinding(ExecutionCommand cmd,
                                            ResolvedRegistration resolved,
                                            CapabilityRegistration<?, ?, ?> reg,
                                            ExecutionScope scope) {
        AgentDomainMode mode = reg.definition().domainMode();
        var selectedDomain = cmd.planningResult().domain();
        if (mode == AgentDomainMode.NONE) {
            if (selectedDomain.isPresent()) {
                throw new IllegalStateException("NONE domainMode must not have selected domain");
            }
            return new DomainResolution(null, ExecutionValidationProjection.none());
        }
        if (selectedDomain.isEmpty()) {
            if (mode == AgentDomainMode.REQUIRED) {
                throw new IllegalStateException("REQUIRED domainMode requires selected domain");
            }
            return new DomainResolution(null, ExecutionValidationProjection.none());
        }
        DomainExecutionResolution resolution = domainPort.resolve(
                new DomainBindingRequest(resolved, selectedDomain.orElseThrow(),
                        scope, scope.domainMetadataEvidence(), cmd.handle().absoluteDeadline()));
        return new DomainResolution(resolution.binding(), resolution.projection());
    }

    private ExecutionValidationContext buildValidationContext(
            ExecutionCommand cmd, CapabilityRegistration<?, ?, ?> reg,
            ExecutionValidationProjection projection, ExecutionScope scope, AdapterExecutionBinding binding) {
        return new ExecutionValidationContext(
                reg.definition().capabilityId(),
                reg.definition().planKind(),
                reg.definition().domainMode(),
                scope,
                projection,
                binding,
                cmd.planningResult().contextSnapshots(),
                cmd.handle().absoluteDeadline(),
                cmd.cancellation());
    }

    private com.dylan.agent.kernel.registration.ValidatedPlanHandle validatePlan(
            ExecutionCommand cmd,
            CapabilityRegistration<?, ?, ?> reg,
            ExecutionValidationContext valCtx) {
        try {
            return reg.validateRaw(cmd.planningResult().rawPlan(), valCtx);
        } catch (RuntimeException ex) {
            log.warn("计划校验失败: capabilityId={}, planKind={}, rawPlanType={}, reason={}",
                    reg.definition().capabilityId(),
                    reg.definition().planKind(),
                    cmd.planningResult().rawPlan().getClass().getSimpleName(),
                    ex.getMessage());
            return null;
        }
    }

    private void validateSecuredResult(SecuredResult secured,
                                       CapabilityRegistration<?, ?, ?> reg) {
        Objects.requireNonNull(secured, "secured result must not be null");
        if (!secured.outputContract().equals(reg.definition().outputContract())) {
            throw new IllegalStateException("secured result binding mismatch");
        }
    }

    private ExecutionContext buildExecutionContext(
            ExecutionCommand cmd, AdapterExecutionBinding binding) {
        return new ExecutionContext(
                cmd.handle().invocationId(),
                cmd.handle().subject(),
                cmd.handle().owner(),
                cmd.handle().scope(),
                binding,
                cmd.handle().absoluteDeadline(),
                cmd.cancellation());
    }

    private ExecutionFailure failure(ExecutionStage stage, KernelErrorCode errorCode, boolean cancelled) {
        return new ExecutionFailure(stage, errorCode, diagnostics(), cancelled);
    }

    private String diagnostics() {
        return "diag-" + UUID.randomUUID().toString().substring(0, 8);
    }

    private record DomainResolution(AdapterExecutionBinding binding,
                                    ExecutionValidationProjection projection) {
    }
}
