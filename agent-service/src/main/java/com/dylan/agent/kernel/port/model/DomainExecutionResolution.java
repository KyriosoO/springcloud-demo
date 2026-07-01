package com.dylan.agent.kernel.port.model;

import com.dylan.agent.kernel.binding.AdapterExecutionBinding;

import java.util.Objects;

/** Atomic domain execution resolution: binding and validation projection from one evidence view. */
public final class DomainExecutionResolution {

    private final AdapterExecutionBinding binding;
    private final ExecutionValidationProjection projection;

    public DomainExecutionResolution(AdapterExecutionBinding binding,
                                     ExecutionValidationProjection projection) {
        this.binding = Objects.requireNonNull(binding);
        this.projection = Objects.requireNonNull(projection);
        if (projection.adapterRole().isEmpty() || projection.domain().isEmpty()) {
            throw new IllegalArgumentException("domain resolution requires role and domain projection");
        }
        if (!projection.domain().orElseThrow().equals(binding.domain())) {
            throw new IllegalArgumentException("binding/projection domain mismatch");
        }
        if (!projection.adapterRole().orElseThrow().equals(binding.adapterRole())) {
            throw new IllegalArgumentException("binding/projection adapterRole mismatch");
        }
    }

    public AdapterExecutionBinding binding() { return binding; }
    public ExecutionValidationProjection projection() { return projection; }
}
