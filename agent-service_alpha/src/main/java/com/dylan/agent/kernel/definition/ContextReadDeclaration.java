package com.dylan.agent.kernel.definition;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.util.Objects;
import java.util.Set;

public record ContextReadDeclaration(
        RuntimeContextType contextType,
        ContractRef contractRef,
        Class<? extends CapabilityContextPayload> payloadType,
        boolean required,
        Set<String> readableFields) {
    public ContextReadDeclaration {
        Objects.requireNonNull(contextType);
        Objects.requireNonNull(contractRef);
        Objects.requireNonNull(payloadType);
        readableFields = Set.copyOf(readableFields == null ? Set.of() : readableFields);
    }
}
