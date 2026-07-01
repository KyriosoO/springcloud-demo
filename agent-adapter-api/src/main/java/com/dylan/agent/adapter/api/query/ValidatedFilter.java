package com.dylan.agent.adapter.api.query;

import java.util.List;

import com.dylan.agent.api.enums.AgentOperator;

/** Java 校验后的不可变过滤条件，由 FilterNormalizer 产出，传给 Adapter 执行。 */
public final class ValidatedFilter {

    private final String field;
    private final AgentOperator operator;
    private final String value;
    private final List<String> values;

    public ValidatedFilter(String field, AgentOperator operator, String value, List<String> values) {
        this.field = field;
        this.operator = operator;
        this.value = value;
        this.values = values == null ? List.of() : List.copyOf(values);
    }

    public String getField() { return field; }
    public AgentOperator getOperator() { return operator; }
    public String getValue() { return value; }
    public List<String> getValues() { return values; }
}
