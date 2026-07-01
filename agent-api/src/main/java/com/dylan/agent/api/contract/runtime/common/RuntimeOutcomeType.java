package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/** Route/Plan 封闭联合的 discriminator 值。 各 union 只接受自己的合法子集。 */
@Schema(description = "Runtime Outcome 类型 discriminator")
public enum RuntimeOutcomeType {

    @Schema(description = "Route 选择了 capability 和候选 domain")
    DECISION,

    @Schema(description = "Plan 可执行")
    EXECUTABLE,

    @Schema(description = "需要澄清补充信息")
    CLARIFICATION
}
