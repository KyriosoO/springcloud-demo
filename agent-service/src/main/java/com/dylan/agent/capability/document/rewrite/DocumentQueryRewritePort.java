package com.dylan.agent.capability.document.rewrite;

import com.dylan.agent.adapter.api.document.provider.DocumentRewriteOperationRequest;
import com.dylan.agent.adapter.api.document.provider.DocumentUntrustedRewritePayload;
import com.dylan.agent.adapter.api.operation.CapabilityOperationOutcome;

public interface DocumentQueryRewritePort {
    CapabilityOperationOutcome<DocumentUntrustedRewritePayload> rewrite(DocumentRewriteOperationRequest request);
}
