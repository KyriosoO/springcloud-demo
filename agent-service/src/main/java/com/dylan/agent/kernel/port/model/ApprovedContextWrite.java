package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** Boundary-approved context write. Handler cannot construct or replace this value. */
public final class ApprovedContextWrite {

    private final String contextId;
    private final ContextWriteCandidate candidate;
    private final String sourceCapabilityId;
    private final String sourceInvocationId;
    private final Optional<String> sourceDomain;
    private final Instant expiresAt;
    private final long expectedVersion;

    public ApprovedContextWrite(String contextId,
                                ContextWriteCandidate candidate,
                                String sourceCapabilityId,
                                String sourceInvocationId,
                                String sourceDomain,
                                Instant expiresAt,
                                long expectedVersion) {
        this.contextId = Objects.requireNonNull(contextId);
        this.candidate = Objects.requireNonNull(candidate);
        this.sourceCapabilityId = Objects.requireNonNull(sourceCapabilityId);
        this.sourceInvocationId = Objects.requireNonNull(sourceInvocationId);
        this.sourceDomain = Optional.ofNullable(sourceDomain);
        this.expiresAt = Objects.requireNonNull(expiresAt);
        if (expectedVersion < 0) {
            throw new IllegalArgumentException("expectedVersion must be non-negative");
        }
        this.expectedVersion = expectedVersion;
    }

    public String contextId() { return contextId; }
    public ContextWriteCandidate candidate() { return candidate; }
    public ContractRef contractRef() { return candidate.contractRef(); }
    public String sourceCapabilityId() { return sourceCapabilityId; }
    public String sourceInvocationId() { return sourceInvocationId; }
    public Optional<String> sourceDomain() { return sourceDomain; }
    public Instant expiresAt() { return expiresAt; }
    public long expectedVersion() { return expectedVersion; }
}
