package com.dylan.agent.adapter.api;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.plan.AggregateOrderSpec;

/** Agent 聚合结果排序/截断工具，供 AggregatableAdapter 实现复用。 */
public final class AggregateOrderAndLimitHelper {

    private AggregateOrderAndLimitHelper() {
    }

    /** 按 query.orderBy 稳定多级排序，再按 query.maxRows 截断，返回不可变结果。 */
    public static List<Map<String, Object>> orderAndLimit(
            List<Map<String, Object>> rows,
            ValidatedAggregateQuery query) {
        List<Map<String, Object>> result = new ArrayList<>(rows);
        for (int i = query.getOrderBy().size() - 1; i >= 0; i--) {
            AggregateOrderSpec order = query.getOrderBy().get(i);
            result.sort((left, right) -> compareValues(
                    left.get(order.getField()),
                    right.get(order.getField()),
                    "DESC".equals(order.getDirection())));
        }
        if (result.size() <= query.getMaxRows()) {
            return result;
        }
        return List.copyOf(result.subList(0, query.getMaxRows()));
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static int compareValues(Object left, Object right, boolean desc) {
        int value;
        if (left == null && right == null) {
            value = 0;
        } else if (left == null) {
            value = 1;
        } else if (right == null) {
            value = -1;
        } else if (left instanceof Number l && right instanceof Number r) {
            value = Double.compare(l.doubleValue(), r.doubleValue());
        } else if (left instanceof Comparable l && right.getClass().isAssignableFrom(left.getClass())) {
            value = l.compareTo(right);
        } else {
            value = left.toString().compareTo(right.toString());
        }
        return desc ? -value : value;
    }
}
