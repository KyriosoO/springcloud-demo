package com.dylan.agent.api.context;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

/** Java root for persisted capability context payloads. */
public sealed interface CapabilityContextPayload
        permits QueryCapabilityContextPayload, AggregateCapabilityContextPayload {

    RuntimeContextType contextType();
}
