package com.dylan.agent.adapter.api.query;

import java.util.List;

/** Java 校验后的不可变查询，包含 filter、selectFields 和分页参数，由 QueryPlanValidator 产出。 */
public final class ValidatedQuery {

    private final List<ValidatedFilter> filters;
    private final List<String> selectFields;
    private final int page;
    private final int size;

    public ValidatedQuery(List<ValidatedFilter> filters, List<String> selectFields, int page, int size) {
        this.filters = List.copyOf(filters);
        this.selectFields = List.copyOf(selectFields);
        this.page = page;
        this.size = size;
    }

    public List<ValidatedFilter> getFilters() { return filters; }
    public List<String> getSelectFields() { return selectFields; }
    public int getPage() { return page; }
    public int getSize() { return size; }
}
