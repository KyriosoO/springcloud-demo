package com.dylan.transaction.api.model;

import java.util.List;

/**
 * 聚合请求 DTO —— 支持按字段分组 + 多指标统计。
 *
 * <pre>
 *   metrics 格式: {@code OPERATION:FIELD} 或 {@code COUNT}
 *   支持 OPERATION: MAX, MIN, SUM, AVG, COUNT
 *   示例: ["SUM:amount", "AVG:amount", "MAX:amount", "MIN:amount", "COUNT"]
 * </pre>
 */
public class AggregateRequest {
    private Transaction condition;
    private List<String> groupBy;
    private List<String> metrics;

    public AggregateRequest() {}

    public AggregateRequest(Transaction condition, List<String> groupBy, List<String> metrics) {
        this.condition = condition;
        this.groupBy = groupBy;
        this.metrics = metrics;
    }

    public Transaction getCondition() { return condition; }
    public void setCondition(Transaction condition) { this.condition = condition; }
    public List<String> getGroupBy() { return groupBy; }
    public void setGroupBy(List<String> groupBy) { this.groupBy = groupBy; }
    public List<String> getMetrics() { return metrics; }
    public void setMetrics(List<String> metrics) { this.metrics = metrics; }
}
