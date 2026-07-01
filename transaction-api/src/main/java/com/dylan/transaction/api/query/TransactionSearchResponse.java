package com.dylan.transaction.api.query;

import java.util.List;

import com.dylan.transaction.api.model.Transaction;

/**
 * Transaction 分页查询响应。totalExact=false 时 total 为下界。
 */
public class TransactionSearchResponse {

    private List<Transaction> rows;
    private long total;
    private boolean totalExact;
    private int page;
    private int size;

    public TransactionSearchResponse() {
    }

    public List<Transaction> getRows() {
        return rows;
    }

    public void setRows(List<Transaction> rows) {
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
