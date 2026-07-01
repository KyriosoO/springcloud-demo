package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentResponseType;

/** Agent 聊天统一响应。QUERY 返回时 queryParameters/queryResult 非空；AGGREGATE 返回时 aggregateResult 非空；CLARIFY 返回时仅 message/summary 有效。 */
public class AgentChatResponse {

    private String conversationId;
    private String turnId;
    private AgentResponseType type;
    private String message;
    private String summary;
    private AgentQueryParameters queryParameters;
    private AgentQueryResult queryResult;
    private AgentAggregateResult aggregateResult;
    private AgentErrorCode errorCode;

    public AgentChatResponse() {
    }

    public String getConversationId() {
        return conversationId;
    }

    public void setConversationId(String conversationId) {
        this.conversationId = conversationId;
    }

    public String getTurnId() {
        return turnId;
    }

    public void setTurnId(String turnId) {
        this.turnId = turnId;
    }

    public AgentResponseType getType() {
        return type;
    }

    public void setType(AgentResponseType type) {
        this.type = type;
    }

    public String getMessage() {
        return message;
    }

    public void setMessage(String message) {
        this.message = message;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
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

    public AgentAggregateResult getAggregateResult() {
        return aggregateResult;
    }

    public void setAggregateResult(AgentAggregateResult aggregateResult) {
        this.aggregateResult = aggregateResult;
    }

    public AgentErrorCode getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(AgentErrorCode errorCode) {
        this.errorCode = errorCode;
    }
}
