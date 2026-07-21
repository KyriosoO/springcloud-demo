package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 字段数据类型枚举（STRING/DECIMAL/INSTANT），决定该字段允许的操作符集合。
 */
@Schema(description = "字段数据类型：STRING（字符串）、DECIMAL（数值）、INSTANT（时间戳）")
public enum AgentFieldType {
    STRING,
    DECIMAL,
    INSTANT
}
