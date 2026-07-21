package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

/**
 * 过滤后的历史 turn 安全投影。
 *
 * <p>content 只包含过滤后的会话文本，不含 Capability Context、结构化结果、权限事实或系统指令。
 */
@Schema(description = "Runtime turn 投影")
public class RuntimeTurnProjection {

    @Schema(description = "turn role", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotNull
    private RuntimeTurnRole role;

    @Schema(description = "过滤后的会话文本", requiredMode = Schema.RequiredMode.REQUIRED)
    @NotBlank
    @Size(min = 1, max = 4000)
    private String content;

    public RuntimeTurnProjection() {
    }

    public RuntimeTurnRole getRole() { return role; }
    public void setRole(RuntimeTurnRole role) { this.role = role; }
    public String getContent() { return content; }
    public void setContent(String content) { this.content = content; }
}
