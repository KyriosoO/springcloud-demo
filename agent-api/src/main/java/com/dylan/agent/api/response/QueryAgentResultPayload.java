package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;

/** QUERY success payload. */
public final class QueryAgentResultPayload implements AgentResultPayload {

    private AgentQueryParameters queryParameters;
    private AgentQueryResult queryResult;

    public QueryAgentResultPayload() {
    }

    public QueryAgentResultPayload(AgentQueryParameters queryParameters,
                                   AgentQueryResult queryResult) {
        this.queryParameters = queryParameters;
        this.queryResult = queryResult;
    }

    @Override
    public AgentResultKind getResultKind() {
        return AgentResultKind.QUERY;
    }

    public AgentQueryParameters getQueryParameters() {
        return queryParameters;
    }

    public void setQueryParameters(AgentQueryParameters queryParameters) {
        this.queryParameters = queryParameters;
    }

    public AgentQueryResult getQueryResult() {
        return queryResult;
    }

    public void setQueryResult(AgentQueryResult queryResult) {
        this.queryResult = queryResult;
    }
}
