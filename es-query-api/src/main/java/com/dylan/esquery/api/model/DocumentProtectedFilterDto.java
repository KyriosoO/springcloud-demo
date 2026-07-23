package com.dylan.esquery.api.model;

import java.util.List;

/** Spring/Jackson 友好的封闭 protected-filter wire node。 */
public record DocumentProtectedFilterDto(
        Kind kind,
        Field field,
        String value,
        List<String> values,
        List<DocumentProtectedFilterDto> children) {
    public DocumentProtectedFilterDto {
        if (kind == null) throw new IllegalArgumentException("protected filter kind is required");
        values = List.copyOf(values == null ? List.of() : values);
        children = List.copyOf(children == null ? List.of() : children);
        switch (kind) {
            case ALL_OF, ANY_OF -> { if (children.isEmpty() || field != null || value != null || !values.isEmpty()) throw new IllegalArgumentException("invalid composite protected filter"); }
            case EXACT -> { if (field == null || value == null || value.isBlank() || !values.isEmpty() || !children.isEmpty()) throw new IllegalArgumentException("invalid exact protected filter"); }
            case ANY_TERMS, NONE_TERMS -> { if (field == null || values.isEmpty() || value != null || !children.isEmpty()) throw new IllegalArgumentException("invalid terms protected filter"); }
        }
    }
    public enum Kind { ALL_OF, ANY_OF, EXACT, ANY_TERMS, NONE_TERMS }
    public enum Field { TENANT_ID, STATUS, VISIBILITY, USER_IDS, DEPARTMENT_IDS, ROLE_IDS, ATTRIBUTE_KEYS, DOCUMENT_ID }
}
