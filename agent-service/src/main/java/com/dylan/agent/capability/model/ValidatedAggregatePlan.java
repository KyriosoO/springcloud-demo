package com.dylan.agent.capability.model;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AgentIntent;

/** AGGREGATE 意图的校验通过 plan。封装 ValidatedAggregateQuery 和 domain。 */
public final class ValidatedAggregatePlan implements ValidatedCapabilityPlan {

    private final String domain;
    private final ValidatedAggregateQuery aggregate;

    public ValidatedAggregatePlan(String domain, ValidatedAggregateQuery aggregate) {
        this.domain = domain;
        this.aggregate = aggregate;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.AGGREGATE;
    }

    @Override
    public String domain() {
        return domain;
    }

    public ValidatedAggregateQuery aggregate() {
        return aggregate;
    }

    @Override
    public String auditSummary() {
        return "AGGREGATE domain=" + domain
                + " metrics=" + aggregate.getMetrics().size()
                + " groups=" + aggregate.getGroupByFields().size();
    }
}
