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
            if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " contains blank value");
            values.add(value.trim());
        }
        return Collections.unmodifiableSet(values);
    }
}
