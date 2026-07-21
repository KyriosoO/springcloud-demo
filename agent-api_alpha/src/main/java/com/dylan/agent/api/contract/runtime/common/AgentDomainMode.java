package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Capability 对 domain 依赖的三态语义。
 *
 * <p>禁止用 boolean 替代。
 */
@Schema(description = "Capability Domain Mode")
public enum AgentDomainMode {

    @Schema(description = "能力与业务域无关，Plan 不得携带 domain")
    NONE,

    @Schema(description = "能力可以引用业务域，domain 可空")
    OPTIONAL,

    @Schema(description = "能力必须绑定业务域，domain 必填")
    REQUIRED
}
