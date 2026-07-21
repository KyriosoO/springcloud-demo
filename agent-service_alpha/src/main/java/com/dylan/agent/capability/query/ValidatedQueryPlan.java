package com.dylan.agent.capability.query;

import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.validator.ValidatedPlan;

import java.util.Objects;
import java.util.Optional;

public final class ValidatedQueryPlan implements ValidatedPlan {

    private final String capabilityId;
    private final String domain;
    private final ValidatedQuery query;

    ValidatedQueryPlan(String capabilityId, String domain, ValidatedQuery query) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.domain = Objects.requireNonNull(domain);
        this.query = Objects.requireNonNull(query);
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
}
