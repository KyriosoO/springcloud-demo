package com.dylan.esquery.document;

import java.time.Instant;

/** Schema 已声明 business field 的封闭标量值，禁止自由 metadata Map。 */
public sealed interface DocumentBusinessFieldValue permits DocumentBusinessFieldValue.Keyword,
        DocumentBusinessFieldValue.Text, DocumentBusinessFieldValue.DateValue,
        DocumentBusinessFieldValue.IntegerValue, DocumentBusinessFieldValue.BooleanValue {
    String name();
    Object value();

    record Keyword(String name, String value) implements DocumentBusinessFieldValue { public Keyword { require(name, value); } }
    record Text(String name, String value) implements DocumentBusinessFieldValue { public Text { require(name, value); } }
    record DateValue(String name, Instant value) implements DocumentBusinessFieldValue { public DateValue { require(name, value); } }
    record IntegerValue(String name, Long value) implements DocumentBusinessFieldValue { public IntegerValue { require(name, value); } }
    record BooleanValue(String name, Boolean value) implements DocumentBusinessFieldValue { public BooleanValue { require(name, value); } }

    private static void require(String name, Object value) {
        if (name == null || name.isBlank() || value == null || value.toString().isBlank()) {
            throw new IllegalArgumentException("document business field name/value must not be blank");
        }
    }
}
