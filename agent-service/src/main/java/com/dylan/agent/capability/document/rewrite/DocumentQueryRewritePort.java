package com.dylan.agent.capability.document.rewrite;

/** Java 调用 Runtime 获取不可信改写候选的端口。 */
public interface DocumentQueryRewritePort {
    DocumentRewriteResponse rewrite(DocumentRewriteRequest request);
}
