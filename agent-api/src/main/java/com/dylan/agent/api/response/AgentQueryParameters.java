package com.dylan.agent.api.response;

import java.util.List;

/** 响应中的查询参数摘要，包含 domain、filters、selectFields、分页信息。 */
public class AgentQueryParameters {

    private String domain;
    private List<AgentQueryFilterParameter> filters;
    private List<String> selectFields;
    private List<AgentQuerySortParameter> sorts;
    private int page;
    private int size;

    public AgentQueryParameters() {
    }

    public String getDomain() {
        return domain;
    }

    public void setDomain(String domain) {
        this.domain = domain;
    }

    public List<AgentQueryFilterParameter> getFilters() {
        return filters;
    }

    public void setFilters(List<AgentQueryFilterParameter> filters) {
        this.filters = filters;
    }

    public List<String> getSelectFields() {
        return selectFields;
    }

    public void setSelectFields(List<String> selectFields) {
        this.selectFields = selectFields;
    }

    public List<AgentQuerySortParameter> getSorts() {
        return sorts;
    }

    public void setSorts(List<AgentQuerySortParameter> sorts) {
        this.sorts = sorts;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }
}
