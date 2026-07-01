package com.dylan.agent.kernel.port.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** Boundary-approved context write. Handler cannot construct or replace this value. */
public final class ApprovedContextWrite {

    private final String contextId;
    private final ContextRecordKey recordKey;
    private final ContextWriteCandidate candidate;
    private final String sourceCapabilityId;
    private final String sourceInvocationId;
    private final Optional<String> sourceDomain;
    private final Instant expiresAt;
    private final ExpectedContextVersion expectedVersion;

    public ApprovedContextWrite(String contextId,
                                ContextRecordKey recordKey,
                                ContextWriteCandidate candidate,
                                String sourceCapabilityId,
                                String sourceInvocationId,
                                String sourceDomain,
                                Instant expiresAt,
                                ExpectedContextVersion expectedVersion) {
        this.contextId = requireNonBlank(contextId, "contextId");
        this.recordKey = Objects.requireNonNull(recordKey);
        this.candidate = Objects.requireNonNull(candidate);
        this.sourceCapabilityId = requireNonBlank(sourceCapabilityId, "sourceCapabilityId");
        this.sourceInvocationId = requireNonBlank(sourceInvocationId, "sourceInvocationId");
        this.sourceDomain = Optional.ofNullable(sourceDomain)
                .map(value -> requireNonBlank(value, "sourceDomain"));
        this.expiresAt = Objects.requireNonNull(expiresAt);
        this.expectedVersion = Objects.requireNonNull(expectedVersion);
    }

    public String contextId() { return contextId; }
    public ContextRecordKey recordKey() { return recordKey; }
    public ContextWriteCandidate candidate() { return candidate; }
    public ContractRef contractRef() { return candidate.contractRef(); }
    public String sourceCapabilityId() { return sourceCapabilityId; }
    public String sourceInvocationId() { return sourceInvocationId; }
    public Optional<String> sourceDomain() { return sourceDomain; }
    public Instant expiresAt() { return expiresAt; }
    public ExpectedContextVersion expectedVersion() { return expectedVersion; }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return normalized;
    }
}
