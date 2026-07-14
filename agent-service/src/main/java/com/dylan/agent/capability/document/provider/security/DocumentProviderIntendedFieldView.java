package com.dylan.agent.capability.document.provider.security;

import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.util.Comparator;
import java.util.List;
import java.util.Objects;

/** 本次 operation 准备外发的字段视图，不携带字段值。 */
public record DocumentProviderIntendedFieldView(List<CanonicalFieldRef> orderedFields) {
    public DocumentProviderIntendedFieldView {
        orderedFields = Objects.requireNonNull(orderedFields, "orderedFields must not be null").stream()
                .map(field -> Objects.requireNonNull(field, "field must not be null"))
                .distinct()
                .sorted(Comparator.comparing(CanonicalFieldRef::domain).thenComparing(CanonicalFieldRef::field))
                .toList();
    }

    public static DocumentProviderIntendedFieldView queryOnly() {
        return new DocumentProviderIntendedFieldView(List.of());
    }
}
