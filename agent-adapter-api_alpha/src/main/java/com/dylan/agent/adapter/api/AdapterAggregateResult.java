package com.dylan.agent.adapter.api;

import java.util.List;
import java.util.Map;

/** Adapter 返回的聚合结果。每行为 groups + metrics 键值对。 */
public class AdapterAggregateResult {

    private final List<Map<String, Object>> rows;
    private final boolean partial;

    public AdapterAggregateResult(List<Map<String, Object>> rows, boolean partial) {
        this.rows = List.copyOf(rows);
        this.partial = partial;
    }

    public List<Map<String, Object>> getRows() { return rows; }
    public boolean isPartial() { return partial; }
}
