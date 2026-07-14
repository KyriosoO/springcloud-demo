package com.dylan.agent.adapter.api.document.provider;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** DPW-1 与 operation DTO 共用的 Spring-free 结构校验。 */
final class DocumentProviderContractValidation {
    private DocumentProviderContractValidation() {}

    static String text(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
        value.codePoints().forEach(codePoint -> {
            if (Character.isISOControl(codePoint) && !Character.isWhitespace(codePoint)) {
                throw new IllegalArgumentException(name + " contains control characters");
            }
        });
        return value;
    }

    static String digest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be a lowercase SHA-256 digest");
        }
        return value;
    }

    static <T> List<T> list(List<T> values, String name, boolean emptyAllowed) {
        List<T> result = List.copyOf(values == null ? List.of() : values);
        if (!emptyAllowed && result.isEmpty()) throw new IllegalArgumentException(name + " must not be empty");
        return result;
    }

    static void uniqueText(List<String> values, String name) {
        Set<String> seen = new HashSet<>();
        for (String value : values) {
            text(value, name);
            if (!seen.add(value)) throw new IllegalArgumentException(name + " contains duplicates");
        }
    }
}
