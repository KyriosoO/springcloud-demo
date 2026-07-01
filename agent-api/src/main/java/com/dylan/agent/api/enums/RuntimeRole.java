package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 对话中一条消息的角色：USER 或 ASSISTANT。
 */
@Schema(description = "对话角色：USER 或 ASSISTANT")
public enum RuntimeRole {
    USER,
    ASSISTANT
}
