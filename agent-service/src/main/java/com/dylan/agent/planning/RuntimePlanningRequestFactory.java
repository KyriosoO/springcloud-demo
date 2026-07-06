package com.dylan.agent.planning;

import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.AgentRuntimeContract;
import com.dylan.agent.api.contract.runtime.common.RuntimeCapabilityRoutingDescriptor;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainRoutingProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainSchema;
import com.dylan.agent.api.contract.runtime.plan.PlanRequest;
import com.dylan.agent.api.contract.runtime.route.RouteRequest;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.catalog.AvailableCapability;
import com.dylan.agent.metadata.catalog.AvailableCapabilitySnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;
import com.dylan.agent.metadata.profile.internal.ProfileBehaviorProjectionBoundary;
import com.dylan.agent.planning.model.PlanningCommand;

import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 基于 Java 持有的规划事实构造 D01 target Route/Plan 请求。
 */
public final class RuntimePlanningRequestFactory {

    private final DomainMetadataPort domainMetadataPort;
    private final ProfileBehaviorProjectionBoundary profileBehaviorProjectionBoundary;
    private final AgentProperties properties;

    public RuntimePlanningRequestFactory(
            DomainMetadataPort domainMetadataPort,
            ProfileBehaviorProjectionBoundary profileBehaviorProjectionBoundary,
            AgentProperties properties) {
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.profileBehaviorProjectionBoundary = Objects.requireNonNull(profileBehaviorProjectionBoundary);
        this.properties = Objects.requireNonNull(properties);
    }

    public RouteRequest routeRequest(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available) {
        Objects.requireNonNull(command, "command must not be null");
        Objects.requireNonNull(evidence, "evidence must not be null");
        Objects.requireNonNull(available, "available must not be null");

        RouteRequest request = new RouteRequest();
        request.setRequestId(command.handle().requestCorrelationId());
        request.setContractVersion(AgentRuntimeContract.VERSION);
        request.setMessage(command.userMessage());
        request.setHistory(command.history());
        request.setProfileBehavior(profileBehaviorProjectionBoundary.project(evidence));
        request.setCapabilities(available.capabilities().stream()
                .map(RuntimePlanningRequestFactory::capabilityProjection)
                .sorted(Comparator.comparing(RuntimeCapabilityRoutingDescriptor::getCapabilityId))
                .toList());
        request.setDomains(routeDomains(evidence, available));
        request.setAbsoluteDeadline(command.handle().absoluteDeadline());
        request.setRepairLimit(repairLimit(evidence.planningScope().maxRepairAttempts()));
        return request;
    }

    public PlanRequest planRequest(
            PlanningCommand command,
            PlanningAuthorizationEvidence evidence,
            ValidatedRouteDecision routeDecision,
            ResolvedRegistration registration,
            List<RuntimeContextView> contextViews) {
        Objects.requireNonNull(command, "command must not be null");
        Objects.requireNonNull(evidence, "evidence must not be null");
        Objects.requireNonNull(routeDecision, "routeDecision must not be null");
        Objects.requireNonNull(registration, "registration must not be null");

        PlanRequest request = new PlanRequest();
        request.setRequestId(command.handle().requestCorrelationId());
        request.setContractVersion(AgentRuntimeContract.VERSION);
        request.setMessage(command.userMessage());
        request.setHistory(command.history());
        request.setCapabilityId(registration.capabilityId());
        request.setPlanKind(registration.planKind());
        request.setCapability(capabilityProjection(routeDecision.capability()));
        request.setInputSchemaRef(inputSchemaRef(registration.registration().definition().inputContract()));
        routeDecision.domain().ifPresent(request::setDomain);
        planSchema(evidence, registration, routeDecision.domain()).ifPresent(request::setDomainSchema);
        request.setContextViews(List.copyOf(contextViews == null ? List.of() : contextViews));
        request.setAbsoluteDeadline(command.handle().absoluteDeadline());
        request.setRepairLimit(repairLimit(routeDecision.capability().maxRepairAttempts()));
        return request;
    }

    private List<RuntimeDomainRoutingProjection> routeDomains(
            PlanningAuthorizationEvidence evidence,
            AvailableCapabilitySnapshot available) {
        Set<String> domains = available.capabilities().stream()
                .flatMap(capability -> capability.allowedDomains().stream())
                .collect(Collectors.toUnmodifiableSet());
        return domainMetadataPort.routeProjection(
                domains,
                evidence.planningScope(),
                available.domainMetadataEvidence(),
                evidence.evidenceDigest(),
                evidence.absoluteDeadline());
    }

    private Optional<RuntimeDomainSchema> planSchema(
            PlanningAuthorizationEvidence evidence,
            ResolvedRegistration registration,
            Optional<String> selectedDomain) {
        return selectedDomain.flatMap(domain -> registration.registration().definition().adapterRole()
                .map(role -> domainMetadataPort.planSchema(
                        role,
                        domain,
                        evidence.planningScope(),
                        evidence.domainMetadataEvidence(),
                        evidence.absoluteDeadline())));
    }

    private int repairLimit(int scopeLimit) {
        int configured = properties.getRuntime() == null ? 1 : properties.getRuntime().getMaxRepairAttempts();
        return Math.min(configured, scopeLimit);
    }

    private static RuntimeCapabilityRoutingDescriptor capabilityProjection(AvailableCapability capability) {
        RuntimeCapabilityRoutingDescriptor projection = new RuntimeCapabilityRoutingDescriptor();
        projection.setCapabilityId(capability.capabilityId());
        projection.setPlanKind(capability.planKind());
        projection.setDescription(capability.routingDescriptor().modelDescription());
        projection.setApplicability(capability.routingDescriptor().applicability());
        projection.setExclusions(capability.routingDescriptor().exclusions());
        projection.setDomainMode(capability.domainMode());
        projection.setAllowedDomains(capability.allowedDomains().stream().sorted().toList());
        return projection;
    }

    private static String inputSchemaRef(ContractRef contractRef) {
        if (AgentExecutionContracts.QUERY_PLAN.equals(contractRef)) {
            return "#/components/schemas/QueryAgentPlan";
        }
        if (AgentExecutionContracts.AGGREGATE_PLAN.equals(contractRef)) {
            return "#/components/schemas/AggregateAgentPlan";
        }
        if (AgentExecutionContracts.DOCUMENT_PLAN.equals(contractRef)) {
            return "#/components/schemas/DocumentAgentPlan";
        }
        return "#/components/schemas/" + contractRef.schema();
    }
}
