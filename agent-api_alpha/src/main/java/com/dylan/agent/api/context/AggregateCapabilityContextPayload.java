package com.dylan.agent.api.context;

import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.plan.AggregateMetricSpec;
import com.dylan.agent.api.plan.AggregateOrderSpec;

import java.util.List;

/** AGGREGATE 类型的 context payload。 */
public record AggregateCapabilityContextPayload(
        List<AgentFilter> filters,
        List<AggregateMetricSpec> metrics,
        List<String> groupByFields,
        List<AggregateOrderSpec> orderBy,
        int maxRows) implements CapabilityContextPayload {

    public AggregateCapabilityContextPayload {
        filters = List.copyOf(filters == null ? List.of() : filters);
        metrics = List.copyOf(metrics == null ? List.of() : metrics);
        groupByFields = List.copyOf(groupByFields == null ? List.of() : groupByFields);
        orderBy = List.copyOf(orderBy == null ? List.of() : orderBy);
        if (metrics.isEmpty()) {
            throw new IllegalArgumentException("metrics must not be empty");
        }
        if (maxRows <= 0) {
            throw new IllegalArgumentException("maxRows must be positive");
        }
    }

    @Override
    public RuntimeContextType contextType() {
        return RuntimeContextType.AGGREGATE;
    }
}
