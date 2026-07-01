package com.dylan.agent.api.response;

import java.util.Map;

/** 聚合结果中的一行：分组键值对 + 聚合指标值。 */
public class AgentAggregateRow {

    private Map<String, Object> groups;
    private Map<String, Object> metrics;

    public AgentAggregateRow() {
    }

    public Map<String, Object> getGroups() {
        return groups;
    }

    public void setGroups(Map<String, Object> groups) {
        this.groups = groups;
    }

    public Map<String, Object> getMetrics() {
        return metrics;
    }

    public void setMetrics(Map<String, Object> metrics) {
        this.metrics = metrics;
    }
}
