package com.dylan.agent.api.response;

import java.util.List;
import java.util.Map;

/** 查询结果，包含列名、数据行、总数（可能为下界估计）、分页位置。 */
public class AgentQueryResult {

    private List<String> columns;
    private List<Map<String, Object>> rows;
    private long total;
    private boolean totalExact;
    private int page;
    private int size;

    public AgentQueryResult() {
    }

    public List<String> getColumns() {
        return columns;
    }

    public void setColumns(List<String> columns) {
        this.columns = columns;
    }

    public List<Map<String, Object>> getRows() {
        return rows;
    }

    public void setRows(List<Map<String, Object>> rows) {
        this.rows = rows;
    }

    public long getTotal() {
        return total;
    }

    public void setTotal(long total) {
        this.total = total;
    }

    public boolean isTotalExact() {
        return totalExact;
    }

    public void setTotalExact(boolean totalExact) {
        this.totalExact = totalExact;
    }

    public int getPage() {
        return page;
    }

    public void setPage(int page) {
        this.page = page;
    }

    public int getSize() {
        return size;
    }

    public void setSize(int size) {
        this.size = size;
    }
}
