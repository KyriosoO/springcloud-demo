package com.dylan.agent.kernel.port.model;

import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;

import java.time.Instant;
import java.util.Objects;

/** 将已选 domain 解析为一个 binding/projection 对的请求。 */
public final class DomainBindingRequest {

    private final ResolvedRegistration registration;
    private final String selectedDomain;
    private final ExecutionScope executionScope;
    private final DomainMetadataEvidence expectedEvidence;
    private final Instant absoluteDeadline;

    public DomainBindingRequest(ResolvedRegistration registration,
                                String selectedDomain,
                                ExecutionScope executionScope,
                                DomainMetadataEvidence expectedEvidence,
                                Instant absoluteDeadline) {
        this.registration = Objects.requireNonNull(registration);
        this.selectedDomain = Objects.requireNonNull(selectedDomain);
        if (selectedDomain.isBlank()) {
            throw new IllegalArgumentException("selectedDomain must not be blank");
        }
        this.executionScope = Objects.requireNonNull(executionScope);
        this.expectedEvidence = Objects.requireNonNull(expectedEvidence);
        if (!this.expectedEvidence.equals(executionScope.domainMetadataEvidence())) {
            throw new IllegalArgumentException("expected evidence must come from execution scope");
        }
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);
    }

    public ResolvedRegistration registration() { return registration; }
    public String selectedDomain() { return selectedDomain; }
    public ExecutionScope executionScope() { return executionScope; }
    public DomainMetadataEvidence expectedEvidence() { return expectedEvidence; }
    public Instant absoluteDeadline() { return absoluteDeadline; }
}
