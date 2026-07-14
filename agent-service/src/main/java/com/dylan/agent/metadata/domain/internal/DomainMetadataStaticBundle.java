package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.metadata.domain.port.DomainMetadataStaticEvidence;

import java.util.Objects;

/** Catalog 与 RegistrationSet 同批发布的不可变静态 bundle。 */
public record DomainMetadataStaticBundle(
        CanonicalDomainCatalog catalog,
        AdapterRegistrationSet registrations,
        DomainMetadataStaticEvidence staticEvidence) {

    public DomainMetadataStaticBundle {
        Objects.requireNonNull(catalog, "catalog must not be null");
        Objects.requireNonNull(registrations, "registrations must not be null");
        Objects.requireNonNull(staticEvidence, "staticEvidence must not be null");
        if (!catalog.catalogVersion().equals(staticEvidence.catalogVersion())
                || !catalog.canonicalDigest().equals(staticEvidence.catalogDigest())
                || !registrations.adapterRegistrationVersion().equals(staticEvidence.registrationSetVersion())
                || !registrations.canonicalDigest().equals(staticEvidence.registrationDigest())) {
            throw new IllegalArgumentException("static evidence does not match bundle content");
        }
    }
}
