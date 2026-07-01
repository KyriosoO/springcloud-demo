package com.dylan.agent.capability.model;

import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.api.enums.AgentIntent;

/** QUERY 意图的校验通过 plan。封装 ValidatedQuery 和 domain。 */
public final class ValidatedQueryPlan implements ValidatedCapabilityPlan {

    private final String domain;
    private final ValidatedQuery query;

    public ValidatedQueryPlan(String domain, ValidatedQuery query) {
        this.domain = domain;
        this.query = query;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.QUERY;
    }

    @Override
    public String domain() {
        return domain;
    }

    public ValidatedQuery query() {
        return query;
    }

    @Override
    public String auditSummary() {
        return "QUERY domain=" + domain
                + " filters=" + query.getFilters().size();
    }
}
