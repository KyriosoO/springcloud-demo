package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;

/** 文档生成失败后的处理策略。 */
@Schema(description = "文档生成失败后的处理策略")
public enum DocumentGenerationFailurePolicy {
    FALLBACK_EXTRACTIVE,
    REFUSE
}
