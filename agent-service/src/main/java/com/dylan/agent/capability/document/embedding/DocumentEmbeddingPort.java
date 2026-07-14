package com.dylan.agent.capability.document.embedding;

import com.dylan.agent.adapter.api.document.provider.DocumentEmbeddingOperationRequest;
import com.dylan.agent.adapter.api.document.provider.DocumentUntrustedEmbeddingPayload;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;

public interface DocumentEmbeddingPort {
    CapabilityOperationOutcome<DocumentUntrustedEmbeddingPayload> embed(DocumentEmbeddingOperationRequest request);
}
