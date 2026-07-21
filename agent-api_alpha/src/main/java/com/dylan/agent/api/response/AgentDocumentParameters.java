package com.dylan.agent.api.response;

import java.util.List;

/** 响应中的文档执行参数摘要。 */
public class AgentDocumentParameters {

    private String domain;
    private String materialType;
    private String operation;
    private String queryText;
    private List<AgentQueryFilterParameter> filters;
    private List<AgentQuerySortParameter> sorts;
    private int topK;
    private String summaryScope;

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public String getMaterialType() { return materialType; }
    public void setMaterialType(String materialType) { this.materialType = materialType; }
    public String getOperation() { return operation; }
    public void setOperation(String operation) { this.operation = operation; }
    public String getQueryText() { return queryText; }
    public void setQueryText(String queryText) { this.queryText = queryText; }
    public List<AgentQueryFilterParameter> getFilters() { return filters; }
    public void setFilters(List<AgentQueryFilterParameter> filters) { this.filters = filters; }
    public List<AgentQuerySortParameter> getSorts() { return sorts; }
    public void setSorts(List<AgentQuerySortParameter> sorts) { this.sorts = sorts; }
    public int getTopK() { return topK; }
    public void setTopK(int topK) { this.topK = topK; }
    public String getSummaryScope() { return summaryScope; }
    public void setSummaryScope(String summaryScope) { this.summaryScope = summaryScope; }
}
