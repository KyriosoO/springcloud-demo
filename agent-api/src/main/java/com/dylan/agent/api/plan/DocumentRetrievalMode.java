package com.dylan.agent.api.plan;

import io.swagger.v3.oas.annotations.media.Schema;

/** 文档检索模式。 */
@Schema(description = "文档检索模式")
public enum DocumentRetrievalMode {
    KEYWORD,
    VECTOR,
    HYBRID
}
