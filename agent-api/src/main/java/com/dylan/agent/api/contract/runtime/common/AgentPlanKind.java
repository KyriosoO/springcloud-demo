package com.dylan.agent.api.contract.runtime.common;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * Agent Plan 结构类型，只表达结构化 Plan 的类型。
 *
 * <p>不作为权限、Handler Registry key 或审计主键。
 * 不包含 {@code CLARIFY} —— 澄清只能通过 {@code ClarificationRequired} outcome 表达。
 * 每个枚举值即为 JSON discriminator。
 */
@Schema(description = "Agent Plan 结构类型")
public enum AgentPlanKind {

    @Schema(description = "数据查询 plan")
    QUERY,

    @Schema(description = "聚合分析 plan")
    AGGREGATE,

    @Schema(description = "文档检索、问答和总结 plan")
    DOCUMENT
}
