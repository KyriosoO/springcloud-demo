package com.dylan.agent.api.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

/** Agent 聊天请求，包含会话 ID（可选）和用户消息文本。 */
@Schema(description = "Agent 聊天请求")
public class AgentChatRequest {

    @Schema(description = "会话 ID，首次请求为空", nullable = true)
    @Size(max = 64)
    private String conversationId;

    @Schema(description = "用户消息文本", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(max = 2000)
    private String message;

    public AgentChatRequest() {
    }

    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
}
