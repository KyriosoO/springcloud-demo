package com.dylan.agent.api.context;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;

/** 持久化 capability context payload 的 Java 根类型。 */
public sealed interface CapabilityContextPayload
        permits QueryCapabilityContextPayload, AggregateCapabilityContextPayload {

    RuntimeContextType contextType();
}
