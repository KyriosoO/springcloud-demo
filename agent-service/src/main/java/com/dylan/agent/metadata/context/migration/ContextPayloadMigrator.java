package com.dylan.agent.metadata.context.migration;

import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.contract.common.ContractRef;

public interface ContextPayloadMigrator<S extends CapabilityContextPayload, T extends CapabilityContextPayload> {
    ContractRef source();
    Class<S> sourceType();
    ContractRef target();
    Class<T> targetType();
    T migrate(S sourcePayload);
}
