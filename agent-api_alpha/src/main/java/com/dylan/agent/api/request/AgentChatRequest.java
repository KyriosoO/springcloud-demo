package com.dylan.agent.api.request;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
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

    @Schema(description = "请求的文档 Profile 名称；仅作为偏好收窄，不授予权限", nullable = true)
    @Size(max = 64)
    @Pattern(regexp = "[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    private String requestedProfile;

    @Schema(description = "请求的文档资料类型；仅作为语料范围收窄，不授予权限", nullable = true)
    @Size(max = 64)
    @Pattern(regexp = "[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
    private String materialType;

    public AgentChatRequest() {
    }

    public String getConversationId() { return conversationId; }
    public void setConversationId(String conversationId) { this.conversationId = conversationId; }
    public String getMessage() { return message; }
    public void setMessage(String message) { this.message = message; }
    public String getRequestedProfile() { return requestedProfile; }
    public void setRequestedProfile(String requestedProfile) { this.requestedProfile = requestedProfile; }
    public String getMaterialType() { return materialType; }
    public void setMaterialType(String materialType) { this.materialType = materialType; }
}
