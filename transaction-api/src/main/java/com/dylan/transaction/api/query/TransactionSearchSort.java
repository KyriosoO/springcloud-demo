package com.dylan.transaction.api.query;

/** Transaction 查询排序条件。 */
public class TransactionSearchSort {

    private String field;
    private String direction;

    public TransactionSearchSort() {
    }

    public TransactionSearchSort(String field, String direction) {
        this.field = field;
        this.direction = direction;
    }

    public String getField() { return field; }
    public void setField(String field) { this.field = field; }
    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
}
