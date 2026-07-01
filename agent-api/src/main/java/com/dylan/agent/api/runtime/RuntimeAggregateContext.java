package com.dylan.agent.api.runtime;

import java.util.List;

import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;

import jakarta.validation.constraints.Min;

/** 聚合查询上下文，序列化到 agent_turn.query_context_json 供审计及后续分析使用。 */
public class RuntimeAggregateContext {

    private String sourceTurnId;
    private String domain;
    private List<AgentFilter> filters;
    private List<AggregateMetricSpec> metrics;
    private List<String> groupByFields;
    @Min(1)
    private int maxRows;

    public RuntimeAggregateContext() {
    }

    public String getSourceTurnId() { return sourceTurnId; }
    public void setSourceTurnId(String sourceTurnId) { this.sourceTurnId = sourceTurnId; }
    public String getDomain() { return domain; }
    public void setDomain(String domain) { this.domain = domain; }
    public List<AgentFilter> getFilters() { return filters; }
    public void setFilters(List<AgentFilter> filters) { this.filters = filters; }
    public List<AggregateMetricSpec> getMetrics() { return metrics; }
    public void setMetrics(List<AggregateMetricSpec> metrics) { this.metrics = metrics; }
    public List<String> getGroupByFields() { return groupByFields; }
    public void setGroupByFields(List<String> groupByFields) { this.groupByFields = groupByFields; }
    public int getMaxRows() { return maxRows; }
    public void setMaxRows(int maxRows) { this.maxRows = maxRows; }
}
