package com.dylan.agent.api.enums;

import io.swagger.v3.oas.annotations.media.Schema;

/**
 * 查询上下文模式：REPLACE（独立新查询）或 MERGE（在上轮结果上增量修改）。
 */
@Schema(description = "查询上下文模式：REPLACE（独立新查询）或 MERGE（在上轮结果上增量修改）")
public enum QueryContextMode {
    REPLACE,
    MERGE
}
