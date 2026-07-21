package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;

import java.util.Set;

/** Document Provider 的闭集 operation type。 */
public final class DocumentProviderOperationTypes {
    public static final CapabilityOperationType REWRITE = CapabilityOperationType.of("DOCUMENT_REWRITE");
    public static final CapabilityOperationType EMBEDDING = CapabilityOperationType.of("DOCUMENT_EMBEDDING");
    public static final CapabilityOperationType RERANK = CapabilityOperationType.of("DOCUMENT_RERANK");
    public static final CapabilityOperationType GENERATION = CapabilityOperationType.of("DOCUMENT_GENERATION");
    public static final Set<CapabilityOperationType> ALL = Set.of(REWRITE, EMBEDDING, RERANK, GENERATION);

    private DocumentProviderOperationTypes() {}
}
