package com.dylan.agent.capability.document;

import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.validator.ValidatedPlan;

import java.util.Objects;
import java.util.Optional;

public final class ValidatedDocumentPlan implements ValidatedPlan {

    private final String capabilityId;
    private final String domain;
    private final DocumentRetrievalRequest request;

    ValidatedDocumentPlan(String capabilityId, String domain, DocumentRetrievalRequest request) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.domain = Objects.requireNonNull(domain);
        this.request = Objects.requireNonNull(request);
    }

    @Override
    public String capabilityId() {
        return capabilityId;
    }

    @Override
    public AgentPlanKind planKind() {
        return AgentPlanKind.DOCUMENT;
    }

    @Override
    public Optional<String> domain() {
        return Optional.of(domain);
    }

    public DocumentRetrievalRequest request() {
        return request;
    }
}
