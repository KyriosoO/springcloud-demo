package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;

/** AGGREGATE success payload. */
public final class AggregateAgentResultPayload implements AgentResultPayload {

    private AgentAggregateResult aggregateResult;

    public AggregateAgentResultPayload() {
    }

    public AggregateAgentResultPayload(AgentAggregateResult aggregateResult) {
        this.aggregateResult = aggregateResult;
    }

    @Override
    public AgentResultKind getResultKind() {
        return AgentResultKind.AGGREGATE;
    }

    public AgentAggregateResult getAggregateResult() {
        return aggregateResult;
    }

    public void setAggregateResult(AgentAggregateResult aggregateResult) {
        this.aggregateResult = aggregateResult;
    }
}
