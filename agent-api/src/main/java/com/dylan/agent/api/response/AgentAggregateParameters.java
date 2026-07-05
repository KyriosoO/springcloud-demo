package com.dylan.agent.api.response;

import java.util.List;

/** 响应中的聚合参数摘要，包含 domain、filters、metrics、分组、排序和行数上限。 */
public class AgentAggregateParameters {

    private String domain;
    private List<AgentQueryFilterParameter> filters;
    private List<AgentAggregateMetricParameter> metrics;
    private List<String> groupByFields;
    private List<AgentAggregateOrderParameter> orderBy;
    private int maxRows;

    public AgentAggregateParameters() {
    }

    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public List<AgentQueryFilterParameter> getFilters() { return filters; }
    public void setFilters(List<AgentQueryFilterParameter> filters) { this.filters = filters; }
    public List<AgentAggregateMetricParameter> getMetrics() { return metrics; }
    public void setMetrics(List<AgentAggregateMetricParameter> metrics) { this.metrics = metrics; }
    public List<String> getGroupByFields() { return groupByFields; }
    public void setGroupByFields(List<String> groupByFields) { this.groupByFields = groupByFields; }
    public List<AgentAggregateOrderParameter> getOrderBy() { return orderBy; }
    public void setOrderBy(List<AgentAggregateOrderParameter> orderBy) { this.orderBy = orderBy; }
    public int getMaxRows() { return maxRows; }
    public void setMaxRows(int maxRows) { this.maxRows = maxRows; }
}
