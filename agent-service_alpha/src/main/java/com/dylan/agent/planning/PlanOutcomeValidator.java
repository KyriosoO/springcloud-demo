package com.dylan.agent.planning;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.planning.model.PlanningCommand;

import java.util.Objects;

/**
 * PlanOutcome 契约校验。只确认 outcome 与已选 Registration 绑定一致。
 */
public final class PlanOutcomeValidator {

    public ExecutablePlan validate(
            PlanOutcome outcome,
            PlanningCommand command,
            ResolvedRegistration registration) {
        Objects.requireNonNull(outcome, "outcome must not be null");
        Objects.requireNonNull(command, "command must not be null");
        Objects.requireNonNull(registration, "registration must not be null");
        validateCommon(outcome, command);
        if (outcome instanceof ClarificationRequired) {
            throw new PlanClarificationException((ClarificationRequired) outcome);
        }
        if (!(outcome instanceof ExecutablePlan executable)) {
            throw new IllegalArgumentException("unsupported PlanOutcome type");
        }
        if (executable.getPlan() == null || executable.getPlan().getPlanKind() != registration.planKind()) {
            throw new IllegalArgumentException("PlanOutcome planKind mismatch");
        }
        if (!registration.registration().rawPlanType().isInstance(executable.getPlan())) {
            throw new IllegalArgumentException("PlanOutcome raw plan type mismatch");
        }
        return executable;
    }

    private static void validateCommon(PlanOutcome outcome, PlanningCommand command) {
        if (!command.handle().requestCorrelationId().equals(outcome.getRequestId())) {
            throw new IllegalArgumentException("PlanOutcome requestId mismatch");
        }
        if (outcome.getMetadata() == null) {
            throw new IllegalArgumentException("PlanOutcome metadata missing");
        }
        outcome.getMetadata().validateFor(RuntimeOperationType.PLAN);
    }

    public static final class PlanClarificationException extends RuntimeException {
        private final ClarificationRequired clarification;

        PlanClarificationException(ClarificationRequired clarification) {
            super("Plan requested clarification");
            this.clarification = Objects.requireNonNull(clarification);
        }

        public ClarificationRequired clarification() {
            return clarification;
        }
    }
}
