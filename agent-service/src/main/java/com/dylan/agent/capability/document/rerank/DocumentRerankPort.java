package com.dylan.agent.capability.document.rerank;

import com.dylan.agent.adapter.api.document.AdapterDocumentResult;

/** 文档 rerank 端口，输入必须已经过权限过滤和安全投影。 */
public interface DocumentRerankPort {
    AdapterDocumentResult rerank(DocumentRerankRequest request);
}
