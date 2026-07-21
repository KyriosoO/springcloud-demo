package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.DocumentRetrievalResponseBinding;
import com.dylan.agent.capability.document.ValidatedDocumentPlan;
import com.dylan.agent.kernel.core.ExecutionContext;
import com.dylan.agent.capability.document.provider.security.DocumentProviderOutboundPolicyDecision;

/** ECP-1 工厂所需的可信执行绑定。 */
public record EvidenceContextPackageRequest(
        ValidatedDocumentPlan plan,
        ExecutionContext context,
        DocumentRetrievalResponseBinding responseBinding,
        DocumentProviderOutboundPolicyDecision outboundPolicyDecision) {
    public EvidenceContextPackageRequest {
        if (plan == null || context == null || responseBinding == null || outboundPolicyDecision == null) {
            throw new IllegalArgumentException("evidence context package request incomplete");
        }
    }
}
