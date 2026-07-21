package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.provider.DocumentGenerationOperationRequest;
import com.dylan.agent.adapter.api.document.provider.DocumentUntrustedGenerationPayload;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;

public interface DocumentGenerationPort {
    CapabilityOperationOutcome<DocumentUntrustedGenerationPayload> generate(DocumentGenerationOperationRequest request);
}
