package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/** 历史 turn role：只允许 USER/ASSISTANT，禁止 SYSTEM/TOOL。 */
@Schema(description = "Runtime turn role")
public enum RuntimeTurnRole {

    @Schema(description = "用户消息")
    USER,

    @Schema(description = "助手消息")
    ASSISTANT
}
