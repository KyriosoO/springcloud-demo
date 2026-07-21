package com.dylan.agent.capability.document.governance.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import java.util.Map;
public interface DocumentProviderConsumerCoveragePort { Map<String,String> requiredConsumers(CapabilityOperationType operationType); }
