package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainRoutingProjection;
import com.dylan.agent.api.contract.runtime.common.RuntimeDomainSchema;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;

import java.time.Instant;
import java.util.List;
import java.util.Set;

/**
 * D02/D04 seam for canonical domain metadata and adapter availability.
 *
 * <p>D02 only consumes this port. Canonical Catalog, AdapterRegistration and
 * concrete domain facts remain owned by D04.</p>
 */
public interface DomainMetadataPort {

    /**
     * Returns the adapter roles known by the current D04 adapter-registration view.
     *
     * <p>This is consumed only during D02 capability registration validation; it
     * does not expose domain facts or adapter instances.</p>
     */
    Set<AdapterRole> knownRoles();

    DomainMetadataEvidence validateReferences(
            DomainMetadataReferenceSet refs,
            Instant absoluteDeadline);

    DomainAvailabilitySnapshot availability(
            Set<AdapterRole> roles,
            PlanningEffectiveScope scope,
            Instant absoluteDeadline);

    void assertCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline);

    List<RuntimeDomainRoutingProjection> routeProjection(
            Set<String> domains,
            PlanningEffectiveScope scope,
            DomainMetadataEvidence expected,
            String authorizationEvidenceDigest,
            Instant absoluteDeadline);

    RuntimeDomainSchema planSchema(
            AdapterRole role,
            String domain,
            PlanningEffectiveScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline);

    ExecutionValidationProjection executionProjection(
            AdapterRole role,
            String domain,
            ExecutionScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline);

    AdapterExecutionBinding bind(
            AdapterRole role,
            String domain,
            ExecutionScope scope,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline);
}
