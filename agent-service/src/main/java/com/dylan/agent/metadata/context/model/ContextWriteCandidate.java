package com.dylan.agent.metadata.context.model;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.util.Objects;

/** Handler-created context write candidate. Handler never supplies owner/scope/expiry. */
public final class ContextWriteCandidate {

    private final RuntimeContextType contextType;
    private final ContractRef contractRef;
    private final CapabilityContextPayload payload;

    public ContextWriteCandidate(RuntimeContextType contextType,
                                 ContractRef contractRef,
                                 CapabilityContextPayload payload) {
        this.contextType = Objects.requireNonNull(contextType);
        this.contractRef = Objects.requireNonNull(contractRef);
        this.payload = Objects.requireNonNull(payload);
        if (payload.contextType() != contextType) {
            throw new IllegalArgumentException("payload contextType mismatch");
        }
    }

    public RuntimeContextType contextType() { return contextType; }
    public ContractRef contractRef() { return contractRef; }
    public CapabilityContextPayload payload() { return payload; }
}
