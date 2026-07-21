package com.dylan.agent.planning;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.metadata.catalog.AvailableCapability;
import com.dylan.agent.metadata.catalog.AvailableCapabilitySnapshot;
import com.dylan.agent.planning.model.PlanningCommand;

import java.util.Objects;
import java.util.Optional;

/**
 * RouteOutcome 契约校验。只校验 Runtime 输出和 Java 可用能力快照的绑定关系。
 */
public final class RouteOutcomeValidator {

    public ValidatedRouteDecision validate(
            RouteOutcome outcome,
            PlanningCommand command,
            AvailableCapabilitySnapshot available) {
        Objects.requireNonNull(outcome, "outcome must not be null");
        Objects.requireNonNull(command, "command must not be null");
        Objects.requireNonNull(available, "available must not be null");
        validateCommon(outcome, command);
        if (outcome instanceof ClarificationRequired) {
            throw new RouteClarificationException((ClarificationRequired) outcome);
        }
        if (!(outcome instanceof RouteDecision decision)) {
            throw new IllegalArgumentException("unsupported RouteOutcome type");
        }
        AvailableCapability capability = available.getRequired(decision.getCapabilityId());
        Optional<String> domain = normalizeDomain(decision.getDomain());
        validateDomain(capability, domain);
        return new ValidatedRouteDecision(decision, capability, domain);
    }

    private static void validateCommon(RouteOutcome outcome, PlanningCommand command) {
        if (!command.handle().requestCorrelationId().equals(outcome.getRequestId())) {
            throw new IllegalArgumentException("RouteOutcome requestId mismatch");
        }
        if (outcome.getMetadata() == null) {
            throw new IllegalArgumentException("RouteOutcome metadata missing");
        }
        outcome.getMetadata().validateFor(RuntimeOperationType.ROUTE);
    }

    private static void validateDomain(AvailableCapability capability, Optional<String> domain) {
        AgentDomainMode mode = capability.domainMode();
        if (mode == AgentDomainMode.NONE && domain.isPresent()) {
            throw new IllegalArgumentException("RouteDecision domain must be absent for NONE mode");
        }
        if (mode == AgentDomainMode.REQUIRED && domain.isEmpty()) {
            throw new IllegalArgumentException("RouteDecision domain is required");
        }
        domain.ifPresent(value -> {
            if (!capability.allowedDomains().contains(value)) {
                throw new IllegalArgumentException("RouteDecision domain is not available");
            }
        });
    }

    private static Optional<String> normalizeDomain(String domain) {
        if (domain == null || domain.isBlank()) {
            return Optional.empty();
        }
        return Optional.of(domain.trim());
    }

    public static final class RouteClarificationException extends RuntimeException {
        private final ClarificationRequired clarification;

        RouteClarificationException(ClarificationRequired clarification) {
            super("Route requested clarification");
            this.clarification = Objects.requireNonNull(clarification);
        }

        public ClarificationRequired clarification() {
            return clarification;
        }
    }
}
