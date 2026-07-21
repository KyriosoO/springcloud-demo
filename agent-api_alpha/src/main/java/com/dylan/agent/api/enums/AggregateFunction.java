package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/** 聚合函数枚举：COUNT、SUM、AVG、MIN、MAX。 */
@Schema(description = "聚合函数：COUNT（计数）、SUM（求和）、AVG（平均值）、MIN（最小值）、MAX（最大值）")
public enum AggregateFunction {
    @Schema(description = "计数聚合，不需要指定 field")
    COUNT,
    @Schema(description = "求和聚合，需要 DECIMAL 类型 field")
    SUM,
    @Schema(description = "平均值聚合，需要 DECIMAL 类型 field")
    AVG,
    @Schema(description = "最小值聚合，需要 DECIMAL 或 INSTANT 类型 field")
    MIN,
    @Schema(description = "最大值聚合，需要 DECIMAL 或 INSTANT 类型 field")
    MAX
}
