package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.util.Objects;

/** 一个不可变 D04 catalog/registration/availability snapshot。 */
public record DomainMetadataBundle(
        CanonicalDomainCatalog catalog,
        AdapterRegistrationSet registrations,
        AdapterAvailabilitySnapshot availability,
        DomainMetadataEvidence evidence) {

    public DomainMetadataBundle {
        Objects.requireNonNull(catalog, "catalog must not be null");
        Objects.requireNonNull(registrations, "registrations must not be null");
        Objects.requireNonNull(availability, "availability must not be null");
        Objects.requireNonNull(evidence, "evidence must not be null");
    }
}
