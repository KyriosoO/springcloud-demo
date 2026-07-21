package com.dylan.agent.capability.aggregate;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.validator.ValidatedPlan;

import java.util.Objects;
import java.util.Optional;

public final class ValidatedAggregatePlan implements ValidatedPlan {

    private final String capabilityId;
    private final String domain;
    private final ValidatedAggregateQuery aggregate;

    ValidatedAggregatePlan(String capabilityId, String domain, ValidatedAggregateQuery aggregate) {
        this.capabilityId = Objects.requireNonNull(capabilityId);
        this.domain = Objects.requireNonNull(domain);
        this.aggregate = Objects.requireNonNull(aggregate);
    }

    @Override
    public String capabilityId() {
        return capabilityId;
    }

    @Override
    public AgentPlanKind planKind() {
        return AgentPlanKind.AGGREGATE;
    }

    @Override
    public Optional<String> domain() {
        return Optional.of(domain);
    }

    public ValidatedAggregateQuery aggregate() {
        return aggregate;
    }
}
