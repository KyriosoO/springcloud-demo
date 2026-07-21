package com.dylan.agent.adapter.api.document;

import java.util.Objects;
import java.util.regex.Pattern;

/** 文档索引 schema 的不可变引用。 */
public record DocumentSchemaRef(String name, String version, String canonicalDigest) {
    private static final Pattern DIGEST = Pattern.compile("[0-9a-f]{64}");

    public DocumentSchemaRef {
        name = requireText(name, "name");
        version = requireText(version, "version");
        Objects.requireNonNull(canonicalDigest, "canonicalDigest must not be null");
        if (!DIGEST.matcher(canonicalDigest).matches()) {
            throw new IllegalArgumentException("canonicalDigest must be lowercase sha256");
        }
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }
}
