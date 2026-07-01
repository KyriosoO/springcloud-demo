package com.dylan.agent.api.runtime;

import com.dylan.agent.api.enums.RuntimeRole;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

/** 对话轮次摘要，包含角色（USER/ASSISTANT）和内容文本，发送给 Runtime 作为上下文。 */
@Schema(description = "对话轮次摘要")
public class RuntimeTurn {

    @Schema(description = "消息角色", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private RuntimeRole role;

    @Schema(description = "内容文本", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    private String content;

    public RuntimeTurn() {
    }

    public RuntimeRole getRole() { return role; }
    public void setRole(RuntimeRole role) { this.role = role; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
}
