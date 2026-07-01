package com.dylan.agent.metadata.domain.port;

import com.dylan.agent.kernel.binding.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;

import java.time.Instant;
import java.util.Optional;

/**
 * D02/D04 seam for canonical domain metadata and adapter availability.
 *
 * <p>D02 only consumes this port. Canonical Catalog, AdapterRegistration and
 * concrete domain facts remain owned by D04.</p>
 */
public interface DomainMetadataPort {

    DomainMetadataEvidence validateReferences(
            DomainMetadataReferenceSet refs,
            Instant absoluteDeadline);

    DomainAvailabilitySnapshot availability(Instant absoluteDeadline);

    void assertCurrent(DomainMetadataEvidence expected, Instant absoluteDeadline);

    ExecutionValidationProjection executionProjection(
            String capabilityId,
            Optional<String> domain,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline);

    AdapterExecutionBinding bind(
            String capabilityId,
            String domain,
            DomainMetadataEvidence expected,
            Instant absoluteDeadline);
}
