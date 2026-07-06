package com.dylan.agent.adapter.api.document;

import java.math.BigDecimal;
import java.util.Map;

/** Adapter 返回的文档证据片段。 */
public class AdapterDocumentEvidence {

    private String documentId;
    private String chunkId;
    private String title;
    private String sourceType;
    private String section;
    private Integer page;
    private String snippet;
    private BigDecimal score;
    private String sourceUri;
    private Map<String, Object> metadata;

    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getChunkId() { return chunkId; }
    public void setChunkId(String chunkId) { this.chunkId = chunkId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public String getSection() { return section; }
    public void setSection(String section) { this.section = section; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public String getSnippet() { return snippet; }
    public void setSnippet(String snippet) { this.snippet = snippet; }
    public BigDecimal getScore() { return score; }
    public void setScore(BigDecimal score) { this.score = score; }
    public String getSourceUri() { return sourceUri; }
    public void setSourceUri(String sourceUri) { this.sourceUri = sourceUri; }
    public Map<String, Object> getMetadata() { return metadata; }
    public void setMetadata(Map<String, Object> metadata) { this.metadata = metadata; }
}
