package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;
import com.fasterxml.jackson.annotation.JsonProperty;

/** AGGREGATE 成功结果 payload。 */
public final class AggregateAgentResultPayload implements AgentResultPayload {

    private AgentAggregateResult aggregateResult;

    public AggregateAgentResultPayload() {
    }

    public AggregateAgentResultPayload(AgentAggregateResult aggregateResult) {
        this.aggregateResult = aggregateResult;
    }

    @Override
    @JsonProperty(value = "resultKind", access = JsonProperty.Access.READ_ONLY)
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
