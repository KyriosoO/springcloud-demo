package com.dylan.esquery.document;

import java.util.Optional;

public interface ReleaseAttestationTechnicalPort {
    DocumentReleaseAttestation attach(AuthorizedReleaseAttestationCommand command);
    Optional<DocumentReleaseAttestation> read(String physicalIndex);
}
