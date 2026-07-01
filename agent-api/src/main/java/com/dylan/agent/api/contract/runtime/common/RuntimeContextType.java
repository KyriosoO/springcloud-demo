package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/** Context 类型 discriminator。不作为持久化 Context Registry。 */
@Schema(description = "上下文类型")
public enum RuntimeContextType {

    @Schema(description = "查询上下文")
    QUERY,

    @Schema(description = "聚合上下文")
    AGGREGATE
}
