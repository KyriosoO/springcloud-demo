package com.dylan.agent.capability.document.governance.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import java.util.Map;
public final class FailClosedDocumentProviderConsumerCoveragePort implements DocumentProviderConsumerCoveragePort { @Override public Map<String,String> requiredConsumers(CapabilityOperationType operationType){return Map.of();} }
