package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/** Agent RESULT payload 判别字段。 */
@Schema(description = "Agent RESULT payload 类型")
public enum AgentResultKind {
    @Schema(description = "查询结果 payload")
    QUERY,
    @Schema(description = "查询预览结果 payload")
    QUERY_PREVIEW,
    @Schema(description = "聚合结果 payload")
    AGGREGATE
}
