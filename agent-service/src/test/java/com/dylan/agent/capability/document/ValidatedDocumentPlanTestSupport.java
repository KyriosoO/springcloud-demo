package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentGenerationOptions;

public final class ValidatedDocumentPlanTestSupport {

    private ValidatedDocumentPlanTestSupport() {
    }

    public static ValidatedDocumentPlan documentPlan(
            String capabilityId,
            String domain,
            DocumentRetrievalRequest request) {
        return new ValidatedDocumentPlan(capabilityId, domain, request);
    }

    public static ValidatedDocumentPlan documentPlan(
            String capabilityId,
            String domain,
            DocumentRetrievalRequest request,
            DocumentGenerationOptions generationOptions) {
        return new ValidatedDocumentPlan(capabilityId, domain, request, generationOptions);
    }
}
