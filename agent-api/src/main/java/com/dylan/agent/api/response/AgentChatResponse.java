package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentErrorCode;
import com.dylan.agent.api.enums.AgentResponseType;

/** Agent 聊天统一响应。RESULT 返回时 result 非空；CLARIFY 返回时仅 message/summary 有效；ERROR 返回时 errorCode 非空。 */
public class AgentChatResponse {

    private String conversationId;
    private String turnId;
    private AgentResponseType type;
    private String message;
    private String summary;
    private AgentResultPayload result;
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

    public AgentResultPayload getResult() {
        return result;
    }

    public void setResult(AgentResultPayload result) {
        this.result = result;
    }

    public AgentErrorCode getErrorCode() {
        return errorCode;
    }

    public void setErrorCode(AgentErrorCode errorCode) {
        this.errorCode = errorCode;
    }
}
