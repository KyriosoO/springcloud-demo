package com.dylan.agent.api.response;

/** 文档引用。 */
public class AgentDocumentCitation {

    private String citationId;
    private String documentId;
    private String title;
    private String section;
    private Integer page;
    private String sourceUri;
    private String snippet;

    public String getCitationId() { return citationId; }
    public void setCitationId(String citationId) { this.citationId = citationId; }
    public String getDocumentId() { return documentId; }
    public void setDocumentId(String documentId) { this.documentId = documentId; }
    public String getTitle() { return title; }
    public void setTitle(String title) { this.title = title; }
    public String getSection() { return section; }
    public void setSection(String section) { this.section = section; }
    public Integer getPage() { return page; }
    public void setPage(Integer page) { this.page = page; }
    public String getSourceUri() { return sourceUri; }
    public void setSourceUri(String sourceUri) { this.sourceUri = sourceUri; }
    public String getSnippet() { return snippet; }
    public void setSnippet(String snippet) { this.snippet = snippet; }
}
