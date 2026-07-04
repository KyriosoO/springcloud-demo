package com.dylan.agent.persistence.projection;

/**
 * Runtime history projection for completed chat turns.
 */
public class AgentTurnHistoryRow {

    private String userMessage;
    private String assistantMessage;

    public String getUserMessage() { return userMessage; }
    public void setUserMessage(String userMessage) { this.userMessage = userMessage; }
    public String getAssistantMessage() { return assistantMessage; }
    public void setAssistantMessage(String assistantMessage) { this.assistantMessage = assistantMessage; }
}
