package com.dylan.agent.capability.document.rewrite;

import java.util.List;

/** 默认关闭 Runtime 改写，确保未配置 endpoint 时只走 Java 规则抽取。 */
public final class DisabledDocumentQueryRewritePort implements DocumentQueryRewritePort {
    @Override
    public DocumentRewriteResponse rewrite(DocumentRewriteRequest request) {
        return new DocumentRewriteResponse(List.of(), null, null);
    }
}
