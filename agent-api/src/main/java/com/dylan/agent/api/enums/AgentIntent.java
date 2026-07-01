package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/** Agent 顶层意图，表达用户目标而非具体执行方式。 */
@Schema(description = "Agent 顶层意图：QUERY（查询）、CLARIFY（反问澄清）、AGGREGATE（聚合分析）")
public enum AgentIntent {
    @Schema(description = "数据查询意图，需要生成 QUERY plan")
    QUERY,
    @Schema(description = "反问澄清意图，信息不足时向用户询问更多条件")
    CLARIFY,
    @Schema(description = "聚合分析意图，需要生成 AGGREGATE plan")
    AGGREGATE
}
