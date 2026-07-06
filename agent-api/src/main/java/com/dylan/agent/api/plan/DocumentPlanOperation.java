package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;

/** 文档能力操作类型。 */
@Schema(name = "DocumentPlanOperation", description = "文档能力操作类型")
public enum DocumentPlanOperation {

    @Schema(description = "文档检索")
    SEARCH,

    @Schema(description = "基于文档证据回答问题")
    ANSWER,

    @Schema(description = "基于文档证据总结")
    SUMMARIZE
}
