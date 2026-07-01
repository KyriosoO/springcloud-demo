package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/** Agent 聊天响应类型：RESULT（结果）、CLARIFY（反问）、ERROR（错误）。 */
@Schema(description = "Agent 聊天响应类型")
public enum AgentResponseType {
    @Schema(description = "结果")
    RESULT,
    @Schema(description = "反问澄清")
    CLARIFY,
    @Schema(description = "错误")
    ERROR
}
