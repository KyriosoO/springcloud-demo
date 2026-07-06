package com.dylan.agent.adapter.api;

import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;

/** 文档检索 Adapter SPI，接收 Java 已验证的文档检索请求。 */
public interface DocumentRetrievableAdapter extends AgentAdapterPort {

    /** 执行文档检索、问答或总结候选证据召回。 */
    AdapterDocumentResult retrieve(DocumentRetrievalRequest request);
}
