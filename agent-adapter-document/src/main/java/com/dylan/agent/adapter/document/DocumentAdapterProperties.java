package com.dylan.agent.adapter.document;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent.document-adapter")
public class DocumentAdapterProperties {

    private String indexPrefix = "agent-doc-";
    private String defaultTitleField = "title";
    private String defaultSnippetField = "content";
    private String sourceTypeField = "sourceType";
    private String sectionField = "section";
    private String pageField = "page";
    private String sourceUriField = "sourceUri";

    public String getIndexPrefix() { return indexPrefix; }
    public void setIndexPrefix(String indexPrefix) { this.indexPrefix = indexPrefix; }
    public String getDefaultTitleField() { return defaultTitleField; }
    public void setDefaultTitleField(String defaultTitleField) { this.defaultTitleField = defaultTitleField; }
    public String getDefaultSnippetField() { return defaultSnippetField; }
    public void setDefaultSnippetField(String defaultSnippetField) { this.defaultSnippetField = defaultSnippetField; }
    public String getSourceTypeField() { return sourceTypeField; }
    public void setSourceTypeField(String sourceTypeField) { this.sourceTypeField = sourceTypeField; }
    public String getSectionField() { return sectionField; }
    public void setSectionField(String sectionField) { this.sectionField = sectionField; }
    public String getPageField() { return pageField; }
    public void setPageField(String pageField) { this.pageField = pageField; }
    public String getSourceUriField() { return sourceUriField; }
    public void setSourceUriField(String sourceUriField) { this.sourceUriField = sourceUriField; }
}
