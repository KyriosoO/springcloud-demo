package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;
import com.fasterxml.jackson.annotation.JsonProperty;

/** DOCUMENT 成功结果 payload。 */
public final class DocumentAgentResultPayload implements AgentResultPayload {

    private AgentDocumentParameters documentParameters;
    private AgentDocumentResult documentResult;

    public DocumentAgentResultPayload() {
    }

    public DocumentAgentResultPayload(AgentDocumentParameters documentParameters,
                                      AgentDocumentResult documentResult) {
        this.documentParameters = documentParameters;
        this.documentResult = documentResult;
    }

    @Override
    @JsonProperty(value = "resultKind", access = JsonProperty.Access.READ_ONLY)
    public AgentResultKind getResultKind() {
        return AgentResultKind.DOCUMENT;
    }

    public AgentDocumentParameters getDocumentParameters() { return documentParameters; }
    public void setDocumentParameters(AgentDocumentParameters documentParameters) { this.documentParameters = documentParameters; }
    public AgentDocumentResult getDocumentResult() { return documentResult; }
    public void setDocumentResult(AgentDocumentResult documentResult) { this.documentResult = documentResult; }
}
