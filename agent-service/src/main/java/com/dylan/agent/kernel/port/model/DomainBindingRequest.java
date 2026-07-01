package com.dylan.agent.kernel.port.model;

import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;

import java.time.Instant;
import java.util.Objects;

/** Request for resolving a selected domain into one binding/projection pair. */
public final class DomainBindingRequest {

    private final ResolvedRegistration registration;
    private final String selectedDomain;
    private final ExecutionScope executionScope;
    private final Instant absoluteDeadline;

    public DomainBindingRequest(ResolvedRegistration registration,
                                String selectedDomain,
                                ExecutionScope executionScope,
                                Instant absoluteDeadline) {
        this.registration = Objects.requireNonNull(registration);
        this.selectedDomain = Objects.requireNonNull(selectedDomain);
        if (selectedDomain.isBlank()) {
            throw new IllegalArgumentException("selectedDomain must not be blank");
        }
        this.executionScope = Objects.requireNonNull(executionScope);
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);
    }

    public ResolvedRegistration registration() { return registration; }
    public String selectedDomain() { return selectedDomain; }
    public ExecutionScope executionScope() { return executionScope; }
    public Instant absoluteDeadline() { return absoluteDeadline; }
}
