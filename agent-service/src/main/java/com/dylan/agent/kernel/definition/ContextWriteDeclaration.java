package com.dylan.agent.kernel.definition;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

import java.time.Duration;
import java.util.Objects;
import java.util.Set;

public record ContextWriteDeclaration(
        RuntimeContextType contextType,
        ContractRef contractRef,
        Class<? extends CapabilityContextPayload> payloadType,
        Duration maxTtl,
        Set<String> writableFields) {
    public ContextWriteDeclaration {
        Objects.requireNonNull(contextType);
        Objects.requireNonNull(contractRef);
        Objects.requireNonNull(payloadType);
        Objects.requireNonNull(maxTtl);
        if (maxTtl.isNegative() || maxTtl.isZero()) {
            throw new IllegalArgumentException("maxTtl must be positive");
        }
        writableFields = Set.copyOf(writableFields == null ? Set.of() : writableFields);
    }
}
