package com.dylan.agent.api.contract.runtime.clarification;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Runtime 澄清原因码。每个 reasonCode 只绑定一个合法 args subtype 和 operation。
 *
 * <p>新增同 Plan Kind capability 不增加专用澄清类型。
 */
@Schema(description = "澄清原因码")
public enum ClarificationReasonCode {

    @Schema(description = "无法在授权 descriptor 中选择唯一 capability")
    CAPABILITY_AMBIGUOUS,

    @Schema(description = "未指定 domain")
    DOMAIN_REQUIRED,

    @Schema(description = "domain 歧义")
    DOMAIN_AMBIGUOUS,

    @Schema(description = "缺少必要字段")
    FIELD_REQUIRED,

    @Schema(description = "字段禁止访问")
    FIELD_FORBIDDEN,

    @Schema(description = "缺少必要值")
    VALUE_REQUIRED,

    @Schema(description = "值歧义")
    VALUE_AMBIGUOUS
}
