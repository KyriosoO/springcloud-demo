package com.dylan.esquery.api.model.document;

import java.util.List;

/** 封闭 caller filter wire node。 */
public record DocumentCallerFilterNode(String field, Operator operator, String value, List<String> values) {
    public DocumentCallerFilterNode {
        if(field==null||field.isBlank()||operator==null)throw new IllegalArgumentException("caller filter invalid");
        values=List.copyOf(values==null?List.of():values);
    }
    public enum Operator { EQ, IN, CONTAINS, CONTAINS_ANY, GT, GTE, LT, LTE }
}
