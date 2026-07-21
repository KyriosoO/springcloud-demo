package com.dylan.agent.api.contract.runtime.error;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Runtime 错误码。不包含 capability/domain/planKind 专用码，不包含可重试建议。
 */
@Schema(description = "Runtime 错误码")
public enum RuntimeErrorCode {

    @Schema(description = "请求契约错误")
    CONTRACT_INVALID,

    @Schema(description = "服务认证被拒绝")
    AUTHENTICATION_FAILED,

    @Schema(description = "provider 不可用")
    PROVIDER_UNAVAILABLE,

    @Schema(description = "deadline 已到期")
    DEADLINE_EXCEEDED,

    @Schema(description = "repair 次数已耗尽")
    OUTPUT_REPAIR_EXHAUSTED,

    @Schema(description = "Runtime 内部错误")
    INTERNAL_ERROR
}
