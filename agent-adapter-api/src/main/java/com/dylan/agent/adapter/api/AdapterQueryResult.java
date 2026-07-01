package com.dylan.agent.adapter.api;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Adapter 返回的查询结果，包含原始数据行、总数、精确定位标记和分页位置。 */
public class AdapterQueryResult {

    private final List<Map<String, Object>> rows;
    private final long total;
    private final boolean totalExact;
    private final int page;
    private final int size;

    public AdapterQueryResult(List<Map<String, Object>> rows, long total, int page, int size) {
        this(rows, total, true, page, size);
    }

    public AdapterQueryResult(List<Map<String, Object>> rows, long total, boolean totalExact, int page, int size) {
        this.rows = rows.stream()
                .map(row -> Collections.unmodifiableMap(new LinkedHashMap<>(row)))
                .toList();
        this.total = total;
        this.totalExact = totalExact;
        this.page = page;
        this.size = size;
    }

    public List<Map<String, Object>> getRows() { return rows; }
    public long getTotal() { return total; }
    public boolean isTotalExact() { return totalExact; }
    public int getPage() { return page; }
    public int getSize() { return size; }
}
