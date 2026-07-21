package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 查询操作符枚举。atomic（EQ/CONTAINS/STARTS_WITH）、multi-value（IN/CONTAINS_ANY/STARTS_WITH_ANY）、range（GT/LT）。
 */
@Schema(description = "查询操作符：EQ/CONTAINS/STARTS_WITH（单值）、IN/CONTAINS_ANY/STARTS_WITH_ANY（多值）、GT/LT（范围）")
public enum AgentOperator {
    EQ,
    CONTAINS,
    CONTAINS_ANY,
    STARTS_WITH,
    STARTS_WITH_ANY,
    IN,
    GT,
    LT
}
