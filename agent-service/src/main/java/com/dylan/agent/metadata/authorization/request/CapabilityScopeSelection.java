package com.dylan.agent.metadata.authorization.request;

import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

/** Selected capability/domain/context tuple frozen after Plan succeeds. */
public record CapabilityScopeSelection(
        ResolvedRegistration registration,
        Optional<String> selectedDomain,
        List<ContextSnapshot> contextSnapshots,
        DomainMetadataEvidence domainMetadataEvidence) {
    public CapabilityScopeSelection {
        Objects.requireNonNull(registration, "registration must not be null");
        selectedDomain = Objects.requireNonNull(selectedDomain, "selectedDomain must not be null")
                .map(value -> {
                    if (value.isBlank()) {
                        throw new IllegalArgumentException("selectedDomain must not be blank");
                    }
                    return value.trim();
                });
        contextSnapshots = List.copyOf(contextSnapshots == null ? List.of() : contextSnapshots);
        Objects.requireNonNull(domainMetadataEvidence, "domainMetadataEvidence must not be null");
    }
}
