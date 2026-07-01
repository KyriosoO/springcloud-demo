package com.dylan.agent.metadata.context.model;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.InvocationScope;

import java.time.Instant;
import java.util.Objects;
import java.util.Optional;

/** Request-local typed context snapshot consumed by Planning/Core. */
public final class ContextSnapshot {

    private final String contextId;
    private final String requestCorrelationId;
    private final ContextOwnerRef owner;
    private final InvocationScope scope;
    private final RuntimeContextType contextType;
    private final Optional<String> sourceDomain;
    private final ContractRef storedContractRef;
    private final ContractRef effectiveContractRef;
    private final long recordVersion;
    private final Instant expiresAt;
    private final CapabilityContextPayload payload;

    public ContextSnapshot(String contextId,
                           String requestCorrelationId,
                           ContextOwnerRef owner,
                           InvocationScope scope,
                           RuntimeContextType contextType,
                           String sourceDomain,
                           ContractRef storedContractRef,
                           ContractRef effectiveContractRef,
                           long recordVersion,
                           Instant expiresAt,
                           CapabilityContextPayload payload) {
        this.contextId = Objects.requireNonNull(contextId);
        this.requestCorrelationId = Objects.requireNonNull(requestCorrelationId);
        this.owner = Objects.requireNonNull(owner);
        this.scope = Objects.requireNonNull(scope);
        this.contextType = Objects.requireNonNull(contextType);
        this.sourceDomain = Optional.ofNullable(sourceDomain);
        this.storedContractRef = Objects.requireNonNull(storedContractRef);
        this.effectiveContractRef = Objects.requireNonNull(effectiveContractRef);
        if (recordVersion < 0) {
            throw new IllegalArgumentException("recordVersion must be non-negative");
        }
        this.recordVersion = recordVersion;
        this.expiresAt = Objects.requireNonNull(expiresAt);
        this.payload = Objects.requireNonNull(payload);
    }

    public String contextId() { return contextId; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public ContextOwnerRef owner() { return owner; }
    public InvocationScope scope() { return scope; }
    public RuntimeContextType contextType() { return contextType; }
    public Optional<String> sourceDomain() { return sourceDomain; }
    public ContractRef storedContractRef() { return storedContractRef; }
    public ContractRef effectiveContractRef() { return effectiveContractRef; }
    public long recordVersion() { return recordVersion; }
    public Instant expiresAt() { return expiresAt; }
    public CapabilityContextPayload payload() { return payload; }
}
