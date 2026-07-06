package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;

public final class ValidatedDocumentPlanTestSupport {

    private ValidatedDocumentPlanTestSupport() {
    }

    public static ValidatedDocumentPlan documentPlan(
            String capabilityId,
            String domain,
            DocumentRetrievalRequest request) {
        return new ValidatedDocumentPlan(capabilityId, domain, request);
    }
}
