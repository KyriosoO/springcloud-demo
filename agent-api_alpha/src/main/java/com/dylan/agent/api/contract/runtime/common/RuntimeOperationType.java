package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/** Runtime 操作类型：Route 选择 capability，Plan 生成结构化计划。 */
@Schema(description = "Runtime 操作类型")
public enum RuntimeOperationType {

    @Schema(description = "Route 阶段：选择 capability 和候选 domain")
    ROUTE,

    @Schema(description = "Plan 阶段：生成结构化候选计划")
    PLAN
}
