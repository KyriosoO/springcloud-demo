package com.dylan.agent.capability.document.governance.provider;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderActivationSnapshot;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
public interface DocumentProviderActivationReadView { DocumentProviderActivationSnapshot requireCurrent(CapabilityOperationType operationType); }
