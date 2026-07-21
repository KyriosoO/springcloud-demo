package com.dylan.agent.adapter.transaction;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.api.AdapterAggregateResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.AggregateOrderAndLimitHelper;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;

/** 将 /txn/aggregate 响应归一为 agent 聚合结果行。 */
@Component
public class TransactionAggregateResponseMapper {

    public AdapterAggregateResult toAdapterAggregateResult(
            Map<String, Object> response,
            ValidatedAggregateQuery query) {
        if (response == null) {
            throw new AgentAdapterException("Transaction 聚合响应为空。");
        }
        Object groupsValue = response.get("groups");
        if (!(groupsValue instanceof List<?> groups)) {
            throw new AgentAdapterException("Transaction 聚合响应 groups 非法。");
        }

        List<Map<String, Object>> rows = new ArrayList<>();
        for (Object value : groups) {
            if (!(value instanceof Map<?, ?> rawRow)) {
                throw new AgentAdapterException("Transaction 聚合响应 row 非法。");
            }
            rows.add(toRow(rawRow, query));
        }

        List<Map<String, Object>> ordered = AggregateOrderAndLimitHelper.orderAndLimit(rows, query);
        return new AdapterAggregateResult(ordered, rows.size() > ordered.size());
    }

    private Map<String, Object> toRow(Map<?, ?> rawRow, ValidatedAggregateQuery query) {
        Map<String, Object> row = new LinkedHashMap<>();
        for (String groupField : query.getGroupByFields()) {
            if (!rawRow.containsKey(groupField)) {
                throw new AgentAdapterException(
                        "Transaction 聚合响应缺少 groupBy 字段: " + groupField);
            }
            row.put(groupField, rawRow.get(groupField));
        }
        for (ValidatedAggregateMetric metric : query.getMetrics()) {
            String key = TransactionPlanMapper.downstreamMetricAlias(metric);
            if (!rawRow.containsKey(key) && metric.getFunction() != AggregateFunction.COUNT) {
                throw new AgentAdapterException(
                        "Transaction 聚合响应缺少 metric 字段: " + key);
            }
            row.put(metric.getAlias(), rawRow.get(key));
        }
        return row;
    }
}
