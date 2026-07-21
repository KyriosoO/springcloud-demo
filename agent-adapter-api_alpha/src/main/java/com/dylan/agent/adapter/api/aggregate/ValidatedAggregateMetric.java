package com.dylan.agent.adapter.api.aggregate;

import com.dylan.agent.api.enums.AggregateFunction;

/** Java 校验后的不可变聚合指标。COUNT 时 field 可为 null。 */
public final class ValidatedAggregateMetric {

    private final String alias;
    private final AggregateFunction function;
    private final String field;

    public ValidatedAggregateMetric(String alias, AggregateFunction function, String field) {
        this.alias = alias;
        this.function = function;
        this.field = field;
    }

    public String getAlias() { return alias; }
    public AggregateFunction getFunction() { return function; }
    public String getField() { return field; }
}
