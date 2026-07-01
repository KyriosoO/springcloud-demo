package com.dylan.agent.kernel.port.model;

import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.util.Objects;

/** Atomic domain execution resolution: binding and validation projection from one evidence view. */
public final class DomainExecutionResolution {

    private final AdapterExecutionBinding binding;
    private final ExecutionValidationProjection projection;
    private final DomainMetadataEvidence expectedEvidence;

    public DomainExecutionResolution(AdapterExecutionBinding binding,
                                     ExecutionValidationProjection projection,
                                     DomainMetadataEvidence expectedEvidence) {
        this.binding = Objects.requireNonNull(binding);
        this.projection = Objects.requireNonNull(projection);
        this.expectedEvidence = Objects.requireNonNull(expectedEvidence);
        if (projection.adapterRole().isEmpty() || projection.domain().isEmpty()) {
            throw new IllegalArgumentException("domain resolution requires role and domain projection");
        }
        if (!projection.domain().orElseThrow().equals(binding.domain())) {
            throw new IllegalArgumentException("binding/projection domain mismatch");
        }
        if (!projection.adapterRole().orElseThrow().equals(binding.adapterRole())) {
            throw new IllegalArgumentException("binding/projection adapterRole mismatch");
        }
        if (!binding.adapterRegistrationVersion().equals(expectedEvidence.adapterRegistrationVersion())) {
            throw new IllegalArgumentException("binding adapter registration version mismatch");
        }
        if (!projection.projectionVersion().equals(expectedEvidence.catalogVersion())) {
            throw new IllegalArgumentException("projection catalog version mismatch");
        }
    }

    public AdapterExecutionBinding binding() { return binding; }
    public ExecutionValidationProjection projection() { return projection; }
    public DomainMetadataEvidence expectedEvidence() { return expectedEvidence; }
}
