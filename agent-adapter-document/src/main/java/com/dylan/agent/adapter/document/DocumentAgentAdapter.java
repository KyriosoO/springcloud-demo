package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import feign.FeignException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class DocumentAgentAdapter implements DocumentRetrievableAdapter {

    private static final Logger log = LoggerFactory.getLogger(DocumentAgentAdapter.class);

    private final DocumentSearchClient client;
    private final DocumentRetrievalMapper retrievalMapper;
    private final DocumentEvidenceMapper evidenceMapper;
    private final DocumentAdapterProperties properties;

    public DocumentAgentAdapter(
            DocumentSearchClient client,
            DocumentRetrievalMapper retrievalMapper,
            DocumentEvidenceMapper evidenceMapper,
            DocumentAdapterProperties properties) {
        this.client = client;
        this.retrievalMapper = retrievalMapper;
        this.evidenceMapper = evidenceMapper;
        this.properties = properties;
    }

    @Override
    public AdapterDocumentResult retrieve(DocumentRetrievalRequest request) {
        String index = properties.getIndexPrefix() + request.getDomain();
        String queryDsl = retrievalMapper.toSearchDsl(request);
        try {
            return evidenceMapper.toAdapterResult(client.search(index, queryDsl), request.getTopK());
        } catch (FeignException ex) {
            log.error("Document search Feign error: status={}", ex.status());
            throw new AgentAdapterException("文档检索服务查询失败。", ex);
        }
    }
}
