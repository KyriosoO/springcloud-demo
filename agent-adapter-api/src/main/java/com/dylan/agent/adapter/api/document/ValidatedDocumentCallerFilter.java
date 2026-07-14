package com.dylan.agent.adapter.api.document;

import java.util.List;

/** Validator 产生的封闭 caller filter；不得承载 ACL 字段或自由 DSL。 */
public record ValidatedDocumentCallerFilter(
        String field,
        Operator operator,
        String value,
        List<String> values) {
    public ValidatedDocumentCallerFilter {
        if (field == null || field.isBlank() || operator == null) {
            throw new IllegalArgumentException("document caller filter field/operator required");
        }
        values = List.copyOf(values == null ? List.of() : values);
        if ((operator == Operator.IN || operator == Operator.CONTAINS_ANY) && values.isEmpty()) {
            throw new IllegalArgumentException("document caller filter values required");
        }
        if (operator != Operator.IN && operator != Operator.CONTAINS_ANY
                && (value == null || value.isBlank())) {
            throw new IllegalArgumentException("document caller filter value required");
        }
    }

    public enum Operator { EQ, IN, CONTAINS, CONTAINS_ANY, GT, GTE, LT, LTE }
}
