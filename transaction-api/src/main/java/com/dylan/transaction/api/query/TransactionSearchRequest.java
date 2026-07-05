package com.dylan.transaction.api.query;

import com.dylan.transaction.api.model.Transaction;
import java.util.List;

/**
 * Transaction 分页查询请求，供 Agent Adapter 调用。
 * condition 复用已有 Transaction 模型的 query-by-example 字段。
 */
public class TransactionSearchRequest {

    private Transaction condition;
    private List<TransactionSearchSort> sorts;
    private int page;
    private int size;

    public TransactionSearchRequest() {
    }

    public Transaction getCondition() {
        return condition;
    }

    public void setCondition(Transaction condition) {
        this.condition = condition;
    }

    public List<TransactionSearchSort> getSorts() {
        return sorts;
    }

    public void setSorts(List<TransactionSearchSort> sorts) {
        this.sorts = sorts;
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
