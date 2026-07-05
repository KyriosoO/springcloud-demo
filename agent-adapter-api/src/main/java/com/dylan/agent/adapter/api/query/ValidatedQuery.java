package com.dylan.agent.adapter.api.query;

import java.util.List;

/** Java 校验后的不可变查询，包含 filter、selectFields 和分页参数，由 QueryPlanValidator 产出。 */
public final class ValidatedQuery {

    private final List<ValidatedFilter> filters;
    private final List<String> selectFields;
    private final List<ValidatedSort> sorts;
    private final int page;
    private final int size;

    public ValidatedQuery(List<ValidatedFilter> filters, List<String> selectFields, int page, int size) {
        this(filters, selectFields, List.of(), page, size);
    }

    public ValidatedQuery(List<ValidatedFilter> filters, List<String> selectFields, List<ValidatedSort> sorts, int page, int size) {
        this.filters = List.copyOf(filters);
        this.selectFields = List.copyOf(selectFields);
        this.sorts = List.copyOf(sorts == null ? List.of() : sorts);
        this.page = page;
        this.size = size;
    }

    public List<ValidatedFilter> getFilters() { return filters; }
    public List<String> getSelectFields() { return selectFields; }
    public List<ValidatedSort> getSorts() { return sorts; }
    public int getPage() { return page; }
    public int getSize() { return size; }
}
