package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;
import com.fasterxml.jackson.annotation.JsonProperty;

/** QUERY 预览成功结果 payload。 */
public final class QueryPreviewResultPayload implements AgentResultPayload {

    private AgentQueryParameters queryParameters;
    private QueryPreviewResult previewResult;

    public QueryPreviewResultPayload() {
    }

    public QueryPreviewResultPayload(AgentQueryParameters queryParameters,
                                     QueryPreviewResult previewResult) {
        this.queryParameters = queryParameters;
        this.previewResult = previewResult;
    }

    @Override
    @JsonProperty(value = "resultKind", access = JsonProperty.Access.READ_ONLY)
    public AgentResultKind getResultKind() {
        return AgentResultKind.QUERY_PREVIEW;
    }

    public AgentQueryParameters getQueryParameters() {
        return queryParameters;
    }

    public void setQueryParameters(AgentQueryParameters queryParameters) {
        this.queryParameters = queryParameters;
    }

    public QueryPreviewResult getPreviewResult() {
        return previewResult;
    }

    public void setPreviewResult(QueryPreviewResult previewResult) {
        this.previewResult = previewResult;
    }
}
