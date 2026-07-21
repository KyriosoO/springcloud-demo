package com.dylan.agent.capability.querypreview;

import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.validator.ValidatedPlan;

import java.util.List;
import java.util.Objects;
import java.util.Optional;

public final class ValidatedQueryPreviewPlan implements ValidatedPlan {

    private final String capabilityId;
    private final String domain;
    private final ValidatedQuery query;
    private final List<String> previewFields;
    private final int previewSize;

    public ValidatedQueryPreviewPlan(
            String capabilityId,
            String domain,
            ValidatedQuery query,
            List<String> previewFields,
            int previewSize) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.domain = Objects.requireNonNull(domain);
        this.query = Objects.requireNonNull(query);
        this.previewFields = List.copyOf(Objects.requireNonNull(previewFields));
        if (!this.query.getSelectFields().equals(this.previewFields)) {
            throw new IllegalArgumentException("previewFields must match query selectFields");
        }
        if (this.query.getPage() != 1) {
            throw new IllegalArgumentException("query preview page must be 1");
        }
        if (this.query.getSize() != previewSize) {
            throw new IllegalArgumentException("previewSize must match query size");
        }
        if (previewSize <= 0) {
            throw new IllegalArgumentException("previewSize must be positive");
        }
        this.previewSize = previewSize;
    }

    @Override
    public String capabilityId() {
        return capabilityId;
    }

    @Override
    public AgentPlanKind planKind() {
        return AgentPlanKind.QUERY;
    }

    @Override
    public Optional<String> domain() {
        return Optional.of(domain);
    }

    public ValidatedQuery query() {
        return query;
    }

    public List<String> previewFields() {
        return previewFields;
    }

    public int previewSize() {
        return previewSize;
    }
}
