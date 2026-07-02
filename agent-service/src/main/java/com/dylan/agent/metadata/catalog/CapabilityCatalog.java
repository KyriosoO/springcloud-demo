package com.dylan.agent.metadata.catalog;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.kernel.registration.CapabilityRegistry;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataPort;

import java.time.Clock;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.stream.Collectors;

/** Computes available capabilities from frozen authorization evidence and one D04 availability snapshot. */
public final class CapabilityCatalog {

    private final CapabilityRegistry capabilityRegistry;
    private final DomainMetadataPort domainMetadataPort;
    private final Clock clock;

    public CapabilityCatalog(
            CapabilityRegistry capabilityRegistry,
            DomainMetadataPort domainMetadataPort,
            Clock clock) {
        this.capabilityRegistry = Objects.requireNonNull(capabilityRegistry);
        this.domainMetadataPort = Objects.requireNonNull(domainMetadataPort);
        this.clock = Objects.requireNonNull(clock);
    }

    public AvailableCapabilitySnapshot available(PlanningAuthorizationEvidence evidence) {
        Objects.requireNonNull(evidence, "evidence must not be null");
        Set<AdapterRole> roles = capabilityRegistry.registrations().stream()
                .map(registration -> registration.definition().adapterRole())
                .flatMap(java.util.Optional::stream)
                .collect(Collectors.toUnmodifiableSet());
        var availability = domainMetadataPort.availability(
                roles,
                evidence.planningScope(),
                evidence.absoluteDeadline());
        Map<AdapterRole, Set<String>> domainsByRole = availability.availableDomains();
        List<AvailableCapability> capabilities = capabilityRegistry.registrations().stream()
                .filter(registration -> evidence.planningScope().allowedCapabilityIds()
                        .contains(registration.definition().capabilityId()))
                .map(registration -> {
                    var definition = registration.definition();
                    Set<String> allowedDomains = definition.adapterRole()
                            .map(role -> domainsByRole.getOrDefault(role, Set.of()))
                            .orElse(Set.of());
                    if (definition.domainMode() == AgentDomainMode.REQUIRED && allowedDomains.isEmpty()) {
                        return null;
                    }
                    return new AvailableCapability(
                            definition.capabilityId(),
                            definition.planKind(),
                            definition.domainMode(),
                            definition.routingDescriptor(),
                            allowedDomains,
                            definition.riskLevel(),
                            definition.executionMode(),
                            evidence.planningScope().maxTotalDuration(),
                            evidence.planningScope().maxRepairAttempts(),
                            evidence.planningScope().maxPageSize(),
                            evidence.planningScope().maxResultRows(),
                            evidence.planningScope().maxResultBytes(),
                            registration.identity());
                })
                .filter(Objects::nonNull)
                .toList();
        return new AvailableCapabilitySnapshot(
                evidence.requestCorrelationId(),
                evidence.evidenceDigest(),
                availability.evidence(),
                capabilities,
                clock.instant());
    }
}
