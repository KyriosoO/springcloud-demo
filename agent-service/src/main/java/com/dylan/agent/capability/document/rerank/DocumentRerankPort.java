package com.dylan.agent.capability.document.rerank;

import com.dylan.agent.adapter.api.document.provider.DocumentRerankOperationRequest;
import com.dylan.agent.adapter.api.document.provider.DocumentUntrustedRerankPayload;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;

public interface DocumentRerankPort {
    CapabilityOperationOutcome<DocumentUntrustedRerankPayload> rerank(DocumentRerankOperationRequest request);
}
