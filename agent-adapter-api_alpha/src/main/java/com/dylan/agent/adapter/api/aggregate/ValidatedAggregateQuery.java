package com.dylan.agent.adapter.api.aggregate;

import java.util.List;

import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.api.plan.AggregateOrderSpec;

/** Java 校验后的不可变聚合查询。filter 复用 ValidatedFilter，metric 使用专属模型。maxRows 为全局结果行数上限。 */
public final class ValidatedAggregateQuery {

    private final List<ValidatedFilter> filters;
    private final List<ValidatedAggregateMetric> metrics;
    private final List<String> groupByFields;
    private final List<AggregateOrderSpec> orderBy;
    private final int maxRows;

    public ValidatedAggregateQuery(List<ValidatedFilter> filters,
                                    List<ValidatedAggregateMetric> metrics,
                                    List<String> groupByFields,
                                    List<AggregateOrderSpec> orderBy,
                                    int maxRows) {
        this.filters = List.copyOf(filters);
        this.metrics = List.copyOf(metrics);
        this.groupByFields = List.copyOf(groupByFields);
        this.orderBy = orderBy != null ? List.copyOf(orderBy) : List.of();
        this.maxRows = maxRows;
    }

    public List<ValidatedFilter> getFilters() { return filters; }
    public List<ValidatedAggregateMetric> getMetrics() { return metrics; }
    public List<String> getGroupByFields() { return groupByFields; }
    public List<AggregateOrderSpec> getOrderBy() { return orderBy; }
    public int getMaxRows() { return maxRows; }
}
