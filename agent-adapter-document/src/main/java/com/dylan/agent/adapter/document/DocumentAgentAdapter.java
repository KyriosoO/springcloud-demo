package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.DocumentRetrievableAdapter;
import com.dylan.agent.adapter.api.document.AdapterDocumentResult;
import com.dylan.agent.adapter.api.document.DocumentRetrievalRequest;
import com.dylan.agent.api.plan.DocumentRetrievalMode;
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
        if (request.getAclScope() == null) {
            throw new AgentAdapterException("文档 ACL 安全投影缺失，已拒绝检索。");
        }
        String index = resolveIndex(request.getDomain(), request.getIndexAlias());
        try {
            if (request.getRetrievalMode() == DocumentRetrievalMode.HYBRID) {
                return evidenceMapper.toAdapterResult(
                        client.hybridSearch(index, retrievalMapper.toHybridRequest(request)),
                        request.getTopK());
            }
            if (request.getRetrievalMode() == DocumentRetrievalMode.VECTOR) {
                return evidenceMapper.toAdapterResult(
                        client.vectorSearch(index, retrievalMapper.toVectorRequest(request)),
                        request.getTopK());
            }
            return evidenceMapper.toAdapterResult(
                    client.search(index, retrievalMapper.toSearchDsl(request)),
                    request.getTopK());
        } catch (FeignException ex) {
            log.error("Document search Feign error: status={}", ex.status());
            throw new AgentAdapterException("文档检索服务查询失败。", ex);
        }
    }

    private String resolveIndex(String domain, String requestIndexAlias) {
        if (requestIndexAlias != null && !requestIndexAlias.isBlank()) {
            return requestIndexAlias;
        }
        String index = properties.getIndexByDomain().get(domain);
        if (index == null || index.isBlank()) {
            throw new AgentAdapterException("文档 domain 缺少显式 read alias 映射，已拒绝检索。");
        }
        return index;
    }
}
