package com.dylan.agent.kernel.core;

import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.kernel.registration.CapabilityRegistration;
import com.dylan.agent.kernel.registration.HandlerCandidate;
import com.dylan.agent.kernel.registration.ResolvedRegistration;

import java.util.List;
import java.util.Objects;

/**
 * 所有 capability 共享的可信执行算法，由 D02_01 唯一负责。
 *
 * <p>不按 capabilityId/domain/planKind 分支。不持久化、不调用 Runtime、不重新查询 Registry。
 */
public final class ExecutionCore {

    private final Object authPort; // AuthorizationExecutionPort after D02_03
    private final Object contextPort; // ContextExecutionPort after D02_03
    private final Object domainPort; // DomainExecutionPort after D02_03
    private final Object contextApprovalPort; // ContextApprovalPort after D02_03
    private final Object resultSecurityPort; // ResultSecurityPort after D02_03

    public ExecutionCore(Object authPort, Object contextPort, Object domainPort,
                         Object contextApprovalPort, Object resultSecurityPort) {
        this.authPort = Objects.requireNonNull(authPort);
        this.contextPort = Objects.requireNonNull(contextPort);
        this.domainPort = Objects.requireNonNull(domainPort);
        this.contextApprovalPort = Objects.requireNonNull(contextApprovalPort);
        this.resultSecurityPort = Objects.requireNonNull(resultSecurityPort);
    }

    /**
     * 13 步可信执行算法。步骤不可跳过。任何失败都不调用后续阶段。
     *
     * <p>D02_01 阶段 port 实现尚未就绪，Core 算法骨架就绪后由 D03 完成集成。
     */
    public ExecutionOutcome execute(ExecutionCommand command) {
        Objects.requireNonNull(command);

        // Step 1: Validate invocation/deadline/cancellation
        if (command.handle().isExpired(java.time.Clock.systemUTC())) {
            return new ExecutionFailure.Impl("EXECUTION_PREFLIGHT", "DEADLINE_EXCEEDED",
                    diagnostics(), false);
        }

        // Step 2: Validate ResolvedRegistration identity and immutability
        ResolvedRegistration resolved = validateRegistrationIdentity(command);

        // Step 3: Validate capabilityId/planKind/raw subtype binding
        CapabilityRegistration<?, ?, ?> reg = resolved.registration();
        validateBinding(command, reg);

        // Step 4: Authorization recheck — D02_03 port
        Object execScope = executeAuthRecheck(command);

        // Step 5: Context currentness — D02_03 port
        executeContextRevalidation(command);

        // Step 6: Domain Mode + Adapter Execution Binding — D02_03 port
        AgentDomainMode domainMode = reg.definition().domainMode();
        Object adapterBinding = resolveBinding(reg, domainMode, execScope);

        // Step 7: Build ExecutionValidationContext
        ExecutionValidationContext valCtx = buildValidationContext(
                command, reg, domainMode, execScope, adapterBinding);

        // Step 8: Invoke Validator
        var handle = reg.validateRaw(
                command.planningResult().rawPlan(), valCtx);

        // Step 9: Build ExecutionContext
        ExecutionContext execCtx = buildExecutionContext(command, adapterBinding);

        // Step 10: Invoke Handler
        var candidate = reg.executeValidated(handle, execCtx);

        // Step 11: Validate output type
        reg.validateOutput(candidate.output());

        // Step 12: Result security + Context write approval — D02_03 ports
        Object secured = executeResultSecurity(
                candidate.output(), reg.definition().outputContract(), execScope);
        List<Object> approvedWrites = executeContextApproval(candidate, reg, execScope);

        // Step 13: Return success
        return new ExecutionSuccess.Impl(secured, approvedWrites,
                reg.definition().capabilityId(), reg.definition().planKind());
    }

    private ResolvedRegistration validateRegistrationIdentity(ExecutionCommand cmd) {
        var r = cmd.planningResult().resolvedRegistration();
        if (!(r instanceof ResolvedRegistration)) {
            return failBinding("registration identity check failed");
        }
        ResolvedRegistration reg = (ResolvedRegistration) r;
        reg.validateIdentity();
        return reg;
    }

    private void validateBinding(ExecutionCommand cmd, CapabilityRegistration<?, ?, ?> reg) {
        var raw = cmd.planningResult().rawPlan();
        if (!reg.rawPlanType().isInstance(raw)) {
            failBinding("raw plan subtype mismatch");
        }
    }

    private Object executeAuthRecheck(ExecutionCommand cmd) {
        // D02_03: return ((AuthorizationExecutionPort) authPort).recheck(
        //     cmd.planningResult().authorizationSnapshot(), cmd.handle());
        return new Object(); // placeholder
    }

    private void executeContextRevalidation(ExecutionCommand cmd) {
        // D02_03: for each ContextSnapshot, revalidate owner/scope/schema/version/TTL
    }

    private Object resolveBinding(CapabilityRegistration<?, ?, ?> reg,
                                   AgentDomainMode mode, Object scope) {
        if (mode == AgentDomainMode.NONE) return null;
        // D02_03: return ((DomainExecutionPort) domainPort).resolve(...);
        return new Object(); // placeholder
    }

    private ExecutionValidationContext buildValidationContext(
            ExecutionCommand cmd, CapabilityRegistration<?, ?, ?> reg,
            AgentDomainMode mode, Object scope, Object binding) {
        return new ExecutionValidationContext(
                reg.definition().capabilityId(),
                reg.definition().planKind(),
                mode,
                scope,
                new Object(), // D02_03 projection placeholder
                binding,
                List.of(),    // D02_03 context snapshots
                cmd.handle().absoluteDeadline(),
                cmd.cancellation());
    }

    private ExecutionContext buildExecutionContext(
            ExecutionCommand cmd, Object binding) {
        return new ExecutionContext(
                cmd.handle().invocationId(),
                cmd.handle().subject(),
                cmd.handle().owner(),
                cmd.handle().scope(),
                binding,
                cmd.handle().absoluteDeadline(),
                cmd.cancellation());
    }

    private Object executeResultSecurity(
            Object output, Object outputContract, Object scope) {
        // D02_03: return ((ResultSecurityPort) resultSecurityPort).secure(...);
        return output; // pass-through placeholder
    }

    private List<Object> executeContextApproval(
            HandlerCandidate candidate, CapabilityRegistration<?, ?, ?> reg, Object scope) {
        // D02_03: return ((ContextApprovalPort) contextApprovalPort).approve(...);
        return List.of();
    }

    private ResolvedRegistration failBinding(String msg) {
        // Return a failure outcome directly
        throw new IllegalStateException("BINDING failure: " + msg);
    }

    private String diagnostics() {
        return "diag-" + java.util.UUID.randomUUID().toString().substring(0, 8);
    }
}
