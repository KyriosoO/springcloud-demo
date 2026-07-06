package com.dylan.agent.api.response;

import java.math.BigDecimal;
import java.util.List;

/** 文档检索命中。 */
public class AgentDocumentHit {

    private String documentId;
    private String title;
    private String sourceType;
    private String snippet;
    private BigDecimal score;
    private List<String> citationIds;

    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getSourceType() { return sourceType; }
    public void setSourceType(String sourceType) { this.sourceType = sourceType; }
    public String getSnippet() { return snippet; }
    public void setSnippet(String snippet) { this.snippet = snippet; }
    public BigDecimal getScore() { return score; }
    public void setScore(BigDecimal score) { this.score = score; }
    public List<String> getCitationIds() { return citationIds; }
    public void setCitationIds(List<String> citationIds) { this.citationIds = citationIds; }
}
