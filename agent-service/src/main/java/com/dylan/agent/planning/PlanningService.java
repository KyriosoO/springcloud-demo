package com.dylan.agent.planning;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.PlanOutcome;
import com.dylan.agent.api.contract.runtime.route.RouteOutcome;
import com.dylan.agent.client.AgentRuntimeClient;
import com.dylan.agent.client.AgentRuntimeErrorMapper;
import com.dylan.agent.client.RuntimeOperationException;
import com.dylan.agent.client.RuntimeOperationFailure;
import com.dylan.agent.invocation.model.CancellationToken;
import com.dylan.agent.invocation.model.KernelErrorCode;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.AuthorizationSnapshot;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.authorization.port.AuthorizationPlanningPort;
import com.dylan.agent.metadata.authorization.request.CapabilityScopeSelection;
import com.dylan.agent.metadata.authorization.request.PlanningSecurityRequest;
import com.dylan.agent.metadata.catalog.AvailableCapabilitySnapshot;
import com.dylan.agent.metadata.catalog.CapabilityCatalog;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.context.port.ContextPlanningPort;
import com.dylan.agent.metadata.context.request.ContextReadRequest;
import com.dylan.agent.planning.model.ExecutablePlanningResult;
import com.dylan.agent.planning.model.PlanningCommand;
import com.dylan.agent.planning.model.PlanningFailure;
import com.dylan.agent.planning.model.PlanningFailureException;
import com.dylan.agent.planning.model.PlanningCancellation;
import com.dylan.agent.planning.model.PlanningCancellationException;
import com.dylan.agent.planning.model.PlanningOperationAudit;
import com.dylan.agent.planning.model.PlanningOperationTermination;
import com.dylan.agent.planning.model.PlanningResult;
import com.dylan.agent.planning.model.PlanningStage;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.Optional;

/**
 * D03 Java Planning 入口，负责 Route/Plan Runtime 操作。
 *
 * <p>本服务不调用处理器、适配器、业务服务或终结持久化。</p>
 */
public final class PlanningService {

    private final AuthorizationPlanningPort authorizationPlanningPort;
    private final CapabilityCatalog capabilityCatalog;
    private final RuntimePlanningRequestFactory requestFactory;
    private final AgentRuntimeClient runtimeClient;
    private final RouteOutcomeValidator routeOutcomeValidator;
    private final CapabilitySelectionResolver capabilitySelectionResolver;
    private final ContextPlanningPort contextPlanningPort;
    private final PlanOutcomeValidator planOutcomeValidator;
    private final PlanningClarificationResolver clarificationResolver;
    private final AgentRuntimeErrorMapper runtimeErrorMapper;
    private final Clock clock;

    public PlanningService(
            AuthorizationPlanningPort authorizationPlanningPort,
            CapabilityCatalog capabilityCatalog,
            RuntimePlanningRequestFactory requestFactory,
            AgentRuntimeClient runtimeClient,
            RouteOutcomeValidator routeOutcomeValidator,
            CapabilitySelectionResolver capabilitySelectionResolver,
            ContextPlanningPort contextPlanningPort,
            PlanOutcomeValidator planOutcomeValidator,
            PlanningClarificationResolver clarificationResolver,
            AgentRuntimeErrorMapper runtimeErrorMapper,
            Clock clock) {
        this.authorizationPlanningPort = Objects.requireNonNull(authorizationPlanningPort);
        this.capabilityCatalog = Objects.requireNonNull(capabilityCatalog);
        this.requestFactory = Objects.requireNonNull(requestFactory);
        this.runtimeClient = Objects.requireNonNull(runtimeClient);
        this.routeOutcomeValidator = Objects.requireNonNull(routeOutcomeValidator);
        this.capabilitySelectionResolver = Objects.requireNonNull(capabilitySelectionResolver);
        this.contextPlanningPort = Objects.requireNonNull(contextPlanningPort);
        this.planOutcomeValidator = Objects.requireNonNull(planOutcomeValidator);
        this.clarificationResolver = Objects.requireNonNull(clarificationResolver);
        this.runtimeErrorMapper = Objects.requireNonNull(runtimeErrorMapper);
        this.clock = Objects.requireNonNull(clock);
    }

    public PlanningResult plan(PlanningCommand command, CancellationToken cancellation) {
        Objects.requireNonNull(command, "command must not be null");
        Objects.requireNonNull(cancellation, "cancellation must not be null");
        ensureActive(command, cancellation, PlanningStage.PROFILE_POLICY, null, null, List.of());
        PlanningAuthorizationEvidence evidence = capture(command);
        ensureActive(command, cancellation, PlanningStage.CATALOG, evidence, null, List.of());
        AvailableCapabilitySnapshot available = availableCapabilities(command, evidence);
        ensureActive(command, cancellation, PlanningStage.ROUTE, evidence, available, List.of());
        PlanningOperationAudit routeAudit;
        ValidatedRouteDecision routeDecision;
        try {
            TimedOutcome<RouteOutcome> routed = route(command, evidence, available);
            routeAudit = reported(routed.outcome().getMetadata(), routed.localDurationMs());
            ensureActive(command, cancellation, PlanningStage.ROUTE, evidence, available, List.of(routeAudit));
            try {
                routeDecision = routeOutcomeValidator.validate(routed.outcome(), command, available);
            } catch (RouteOutcomeValidator.RouteClarificationException ex) {
                return clarificationResolver.routeClarification(
                        ex.clarification(),
                        evidence.evidenceDigest(),
                        available.domainMetadataEvidence().safeRef(),
                        routeAudit,
                        command.handle().absoluteDeadline());
            } catch (RuntimeException ex) {
                throw failure(command, PlanningStage.ROUTE, KernelErrorCode.RUNTIME_CONTRACT_INVALID,
                        "planning-route-invalid", evidence, available, List.of(routeAudit));
            }
        } catch (RouteOutcomeValidator.RouteClarificationException ex) {
            return clarificationResolver.routeClarification(
                    ex.clarification(),
                    evidence.evidenceDigest(),
                    available.domainMetadataEvidence().safeRef(),
                    reported(ex.clarification().getMetadata(), 0L),
                    command.handle().absoluteDeadline());
        } catch (RuntimeOperationException ex) {
            throwIfCancellation(command, ex, evidence, available, null);
            throw new PlanningFailureException(runtimeErrorMapper.map(ex, command.handle()));
        } catch (RuntimeException ex) {
            if (ex instanceof PlanningFailureException planningFailure) {
                throw planningFailure;
            }
            throw failure(command, PlanningStage.ROUTE, KernelErrorCode.RUNTIME_CONTRACT_INVALID,
                    "planning-route-invalid", evidence, available, List.of());
        }

        ResolvedRegistration registration = resolveRegistration(command, routeDecision, available, routeAudit);
        ensureActive(command, cancellation, PlanningStage.CONTEXT, evidence, available, List.of(routeAudit));
        ContextBundle contexts = loadContexts(command, evidence, registration, routeAudit);
        ensureActive(command, cancellation, PlanningStage.PLAN, evidence, available, List.of(routeAudit));

        PlanningOperationAudit planAudit;
        ExecutablePlan executable;
        try {
            TimedOutcome<PlanOutcome> planned = plan(command, evidence, routeDecision, registration, contexts.views());
            planAudit = reported(planned.outcome().getMetadata(), planned.localDurationMs());
            ensureActive(command, cancellation, PlanningStage.PLAN, evidence, available, List.of(routeAudit, planAudit));
            try {
                executable = planOutcomeValidator.validate(planned.outcome(), command, registration);
            } catch (PlanOutcomeValidator.PlanClarificationException ex) {
                throwIfPlanFieldForbidden(command, ex, evidence, available, routeAudit, planAudit);
                return clarificationResolver.planClarification(
                        ex.clarification(),
                        routeDecision,
                        registration.registrationIdentity(),
                        evidence.evidenceDigest(),
                        available.domainMetadataEvidence().safeRef(),
                        routeAudit,
                        planAudit,
                        command.handle().absoluteDeadline());
            } catch (RuntimeException ex) {
                throw failure(command, PlanningStage.PLAN, KernelErrorCode.RUNTIME_CONTRACT_INVALID,
                        "planning-plan-invalid", evidence, available, List.of(routeAudit, planAudit));
            }
        } catch (PlanOutcomeValidator.PlanClarificationException ex) {
            throwIfPlanFieldForbidden(command, ex, evidence, available, routeAudit,
                    reported(ex.clarification().getMetadata(), 0L));
            return clarificationResolver.planClarification(
                    ex.clarification(),
                    routeDecision,
                    registration.registrationIdentity(),
                    evidence.evidenceDigest(),
                    available.domainMetadataEvidence().safeRef(),
                    routeAudit,
                    reported(ex.clarification().getMetadata(), 0L),
                    command.handle().absoluteDeadline());
        } catch (RuntimeOperationException ex) {
            throwIfCancellation(command, ex, evidence, available, routeAudit);
            throw new PlanningFailureException(runtimeErrorMapper.map(ex, command.handle(), routeAudit));
        } catch (RuntimeException ex) {
            if (ex instanceof PlanningFailureException planningFailure) {
                throw planningFailure;
            }
            throw failure(command, PlanningStage.PLAN, KernelErrorCode.RUNTIME_CONTRACT_INVALID,
                    "planning-plan-invalid", evidence, available, List.of(routeAudit));
        }

        ensureActive(command, cancellation, PlanningStage.SNAPSHOT_FREEZE, evidence, available, List.of(routeAudit, planAudit));
        AuthorizationSnapshot authorizationSnapshot = freezeAuthorization(
                command, evidence, registration, routeDecision.domain(), contexts.snapshots(), available, routeAudit, planAudit);
        return ExecutablePlanningResult.builder()
                .requestCorrelationId(command.handle().requestCorrelationId())
                .capabilityId(registration.capabilityId())
                .domain(routeDecision.domain().orElse(null))
                .planKind(registration.planKind())
                .resolvedRegistration(registration)
                .rawPlan(executable.getPlan())
                .authorizationSnapshot(authorizationSnapshot)
                .contextSnapshots(contexts.snapshots())
                .routeAudit(routeAudit)
                .planAudit(planAudit)
                .absoluteDeadline(command.handle().absoluteDeadline())
                .build();
    }

    private PlanningAuthorizationEvidence capture(PlanningCommand command) {
        try {
            return authorizationPlanningPort.capture(new PlanningSecurityRequest(
                    command.handle(),
                    command.agentProfileRef(),
                    command.delegationConstraintRef()));
        } catch (RuntimeException ex) {
            throw failure(command, PlanningStage.PROFILE_POLICY, KernelErrorCode.PERMISSION_UNAVAILABLE,
                    "planning-auth-capture", null, null, List.of());
        }
    }

    private void throwIfPlanFieldForbidden(
            PlanningCommand command,
            PlanOutcomeValidator.PlanClarificationException exception,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available,
            PlanningOperationAudit routeAudit,
            PlanningOperationAudit planAudit) {
        if (exception.clarification().getReasonCode()
                != com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode.FIELD_FORBIDDEN) {
            return;
        }
        throw failure(command, PlanningStage.PLAN, KernelErrorCode.FIELD_FORBIDDEN,
                "planning-field-forbidden",
                "没有权限访问请求的字段，请调整字段后重试。",
                evidence, available, List.of(routeAudit, planAudit));
    }

    private AvailableCapabilitySnapshot availableCapabilities(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence) {
        try {
            AvailableCapabilitySnapshot available = capabilityCatalog.available(evidence);
            if (available.capabilities().isEmpty()) {
                throw new IllegalStateException("no available capability");
            }
            return available;
        } catch (RuntimeException ex) {
            throw failure(command, PlanningStage.CATALOG, KernelErrorCode.CATALOG_INCONSISTENT,
                    "planning-catalog", evidence, null, List.of());
        }
    }

    private TimedOutcome<RouteOutcome> route(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available) {
        Instant started = clock.instant();
        RouteOutcome outcome = runtimeClient.route(requestFactory.routeRequest(command, evidence, available));
        return new TimedOutcome<>(outcome, elapsedMillis(started));
    }

    private ResolvedRegistration resolveRegistration(
            PlanningCommand command,
            ValidatedRouteDecision routeDecision,
            AvailableCapabilitySnapshot available,
            PlanningOperationAudit routeAudit) {
        try {
            return capabilitySelectionResolver.resolve(routeDecision, available);
        } catch (RuntimeException ex) {
            throw failure(command, PlanningStage.REGISTRATION, KernelErrorCode.REGISTRATION_MISMATCH,
                    "planning-registration", null, available, List.of(routeAudit));
        }
    }

    private ContextBundle loadContexts(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            ResolvedRegistration registration,
            PlanningOperationAudit routeAudit) {
        List<ContextSnapshot> snapshots = new ArrayList<>();
        List<com.dylan.agent.api.contract.runtime.common.RuntimeContextView> views = new ArrayList<>();
        for (ContextReadDeclaration declaration : registration.registration().definition().contextAccess().reads()) {
            Optional<ContextSnapshot> loaded = contextPlanningPort.load(new ContextReadRequest(
                    command.handle().requestCorrelationId(),
                    command.handle().owner(),
                    command.handle().scope(),
                    declaration,
                    evidence));
            if (loaded.isEmpty()) {
                if (declaration.required()) {
                    throw failure(command, PlanningStage.CONTEXT, KernelErrorCode.CONTEXT_REQUIRED_MISSING,
                            "planning-context-required", evidence, null, List.of(routeAudit));
                }
                continue;
            }
            ContextSnapshot snapshot = loaded.get();
            snapshots.add(snapshot);
            views.add(contextPlanningPort.toRuntimeView(snapshot, declaration, evidence));
        }
        return new ContextBundle(List.copyOf(snapshots), List.copyOf(views));
    }

    private TimedOutcome<PlanOutcome> plan(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            ValidatedRouteDecision routeDecision,
            ResolvedRegistration registration,
            List<com.dylan.agent.api.contract.runtime.common.RuntimeContextView> contextViews) {
        Instant started = clock.instant();
        PlanOutcome outcome = runtimeClient.plan(requestFactory.planRequest(
                command,
                evidence,
                routeDecision,
                registration,
                contextViews));
        return new TimedOutcome<>(outcome, elapsedMillis(started));
    }

    private AuthorizationSnapshot freezeAuthorization(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            ResolvedRegistration registration,
            Optional<String> selectedDomain,
            List<ContextSnapshot> snapshots,
            AvailableCapabilitySnapshot available,
            PlanningOperationAudit routeAudit,
            PlanningOperationAudit planAudit) {
        try {
            return authorizationPlanningPort.freezeCapabilityScope(
                    evidence,
                    new CapabilityScopeSelection(
                            registration,
                            selectedDomain,
                            snapshots,
                            available.domainMetadataEvidence()));
        } catch (RuntimeException ex) {
            throw failure(command, PlanningStage.SNAPSHOT_FREEZE, KernelErrorCode.AUTH_EVIDENCE_CHANGED,
                    "planning-auth-freeze", evidence, available, List.of(routeAudit, planAudit));
        }
    }

    private void ensureActive(
            PlanningCommand command,
            CancellationToken cancellation,
            PlanningStage stage,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available,
            List<PlanningOperationAudit> audits) {
        if (cancellation.isCancelled()) {
            throw cancellation(command, stage, cancellation.reasonCode().orElse(KernelErrorCode.CANCELLED),
                    evidence, available, audits);
        }
        if (!clock.instant().isBefore(command.handle().absoluteDeadline())) {
            throw cancellation(command, stage, KernelErrorCode.DEADLINE_EXCEEDED, evidence, available, audits);
        }
    }

    private void throwIfCancellation(
            PlanningCommand command,
            RuntimeOperationException exception,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available,
            PlanningOperationAudit routeAudit) {
        if (exception.failure() != RuntimeOperationFailure.DEADLINE) {
            return;
        }
        List<PlanningOperationAudit> audits = exception.operation() == RuntimeOperationType.ROUTE
                ? List.of(exception.audit())
                : routeAudit == null ? List.of(exception.audit()) : List.of(routeAudit, exception.audit());
        throw cancellation(command, stage(exception), KernelErrorCode.DEADLINE_EXCEEDED, evidence, available, audits);
    }

    private PlanningStage stage(RuntimeOperationException exception) {
        return switch (exception.operation()) {
            case ROUTE -> PlanningStage.ROUTE;
            case PLAN -> PlanningStage.PLAN;
        };
    }

    private PlanningCancellationException cancellation(
            PlanningCommand command,
            PlanningStage stage,
            KernelErrorCode errorCode,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available,
            List<PlanningOperationAudit> audits) {
        return new PlanningCancellationException(new PlanningCancellation(
                command.handle().requestCorrelationId(),
                stage,
                errorCode,
                evidence == null ? null : evidence.evidenceDigest(),
                available == null ? null : available.domainMetadataEvidence().safeRef(),
                audits));
    }

    private PlanningFailureException failure(
            PlanningCommand command,
            PlanningStage stage,
            KernelErrorCode errorCode,
            String diagnosticId,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available,
            List<PlanningOperationAudit> audits) {
        return failure(command, stage, errorCode, diagnosticId, null, evidence, available, audits);
    }

    private PlanningFailureException failure(
            PlanningCommand command,
            PlanningStage stage,
            KernelErrorCode errorCode,
            String diagnosticId,
            String safeMessage,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available,
            List<PlanningOperationAudit> audits) {
        return new PlanningFailureException(new PlanningFailure(
                command.handle().requestCorrelationId(),
                stage,
                errorCode,
                diagnosticId,
                safeMessage,
                evidence == null ? null : evidence.evidenceDigest(),
                available == null ? null : available.domainMetadataEvidence().safeRef(),
                audits));
    }

    private PlanningOperationAudit reported(
            com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata metadata,
            long localDurationMs) {
        return PlanningOperationAudit.reported(
                metadata,
                Math.max(0L, localDurationMs),
                PlanningOperationTermination.OUTCOME_RECEIVED);
    }

    private long elapsedMillis(Instant started) {
        return Math.max(0L, Duration.between(started, clock.instant()).toMillis());
    }

    private record TimedOutcome<T>(T outcome, long localDurationMs) {
    }

    private record ContextBundle(
            List<ContextSnapshot> snapshots,
            List<com.dylan.agent.api.contract.runtime.common.RuntimeContextView> views) {
    }
}
