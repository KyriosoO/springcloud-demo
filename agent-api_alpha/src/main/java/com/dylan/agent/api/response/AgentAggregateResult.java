package com.dylan.agent.api.response;

import java.util.List;

/** 聚合查询结果：domain、分组字段、指标别名列表、数据行、部分结果标记。 */
public class AgentAggregateResult {

    private String domain;
    private List<String> groupByFields;
    private List<String> metricAliases;
    private List<AgentAggregateRow> rows;
    private boolean partial;

    public AgentAggregateResult() {
    }

    public String getDomain() {
        return domain;
    }

    public void setDomain(String domain) {
        this.domain = domain;
    }

    public List<String> getGroupByFields() {
        return groupByFields;
    }

    public void setGroupByFields(List<String> groupByFields) {
        this.groupByFields = groupByFields;
    }

    public List<String> getMetricAliases() {
        return metricAliases;
    }

    public void setMetricAliases(List<String> metricAliases) {
        this.metricAliases = metricAliases;
    }

    public List<AgentAggregateRow> getRows() {
        return rows;
    }

    public void setRows(List<AgentAggregateRow> rows) {
        this.rows = rows;
    }

    public boolean isPartial() {
        return partial;
    }

    public void setPartial(boolean partial) {
        this.partial = partial;
    }
}
