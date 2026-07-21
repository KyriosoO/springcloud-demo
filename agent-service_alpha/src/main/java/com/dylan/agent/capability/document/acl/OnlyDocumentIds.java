package com.dylan.agent.capability.document.acl;

import java.util.Collections;
import java.util.Set;
import java.util.TreeSet;

public record OnlyDocumentIds(Set<String> documentIds) implements DocumentIdConstraint {
    public OnlyDocumentIds {
        documentIds = stableSet(documentIds, "documentIds");
        if (documentIds.isEmpty()) throw new IllegalArgumentException("documentIds must not be empty");
    }

    static Set<String> stableSet(Set<String> source, String name) {
        if (source == null) throw new IllegalArgumentException(name + " must not be null");
        TreeSet<String> values = new TreeSet<>();
        for (String value : source) {
            values.add(canonicalValue(value, name));
        }
        return Collections.unmodifiableSet(values);
    }

    static String canonicalValue(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " contains blank value");
        String normalized = value.trim();
        if (normalized.codePointCount(0, normalized.length()) > 512
                || normalized.codePoints().anyMatch(Character::isISOControl)) {
            throw new IllegalArgumentException(name + " contains non-canonical value");
        }
        return normalized;
    }
}
