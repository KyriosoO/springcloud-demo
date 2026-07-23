package com.dylan.esquery.document;

/** Schema registry 中业务字段的封闭 ES 标量类型。 */
public record DocumentBusinessFieldDefinition(String name, Type type) {
    public enum Type { KEYWORD, TEXT, DATE, INTEGER, BOOLEAN }
    public DocumentBusinessFieldDefinition {
        if (name == null || !name.matches("[a-z][A-Za-z0-9]{0,127}") || type == null) {
            throw new IllegalArgumentException("document business field definition invalid");
        }
    }
}
