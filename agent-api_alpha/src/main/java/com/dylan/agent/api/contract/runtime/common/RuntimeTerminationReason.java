package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/** Runtime operation 终止原因，不含 provider 原始错误。 */
@Schema(description = "Runtime operation 终止原因")
public enum RuntimeTerminationReason {

    @Schema(description = "正常完成")
    COMPLETED,

    @Schema(description = "返回澄清请求")
    CLARIFICATION,

    @Schema(description = "Java 校验拒绝")
    VALIDATION_REJECTED,

    @Schema(description = "repair 次数已耗尽")
    REPAIR_EXHAUSTED,

    @Schema(description = "deadline 已到期")
    DEADLINE_EXCEEDED,

    @Schema(description = "已取消")
    CANCELLED,

    @Schema(description = "provider 不可用")
    PROVIDER_UNAVAILABLE,

    @Schema(description = "服务认证被拒绝")
    AUTHENTICATION_REJECTED,

    @Schema(description = "Runtime 内部错误")
    INTERNAL_ERROR
}
