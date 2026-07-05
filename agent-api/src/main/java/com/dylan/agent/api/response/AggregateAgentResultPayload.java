package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;
import com.fasterxml.jackson.annotation.JsonProperty;

/** AGGREGATE 成功结果 payload。 */
public final class AggregateAgentResultPayload implements AgentResultPayload {

    private AgentAggregateParameters aggregateParameters;
    private AgentAggregateResult aggregateResult;

    public AggregateAgentResultPayload() {
    }

    public AggregateAgentResultPayload(AgentAggregateResult aggregateResult) {
        this.aggregateResult = aggregateResult;
    }

    public AggregateAgentResultPayload(AgentAggregateParameters aggregateParameters,
                                       AgentAggregateResult aggregateResult) {
        this.aggregateParameters = aggregateParameters;
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

    public AgentAggregateParameters getAggregateParameters() {
        return aggregateParameters;
    }

    public void setAggregateParameters(AgentAggregateParameters aggregateParameters) {
        this.aggregateParameters = aggregateParameters;
    }

    public void setAggregateResult(AgentAggregateResult aggregateResult) {
        this.aggregateResult = aggregateResult;
    }
}
