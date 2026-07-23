package com.dylan.esquery.api.model;

import java.util.regex.Pattern;

/** ES wire 侧文档 schema 安全引用。 */
public record DocumentSchemaRefDto(String name, String version, String canonicalDigest) {
    private static final Pattern DIGEST = Pattern.compile("[0-9a-f]{64}");
    public DocumentSchemaRefDto {
        if (name == null || name.isBlank()) throw new IllegalArgumentException("name must not be blank");
        if (version == null || version.isBlank()) throw new IllegalArgumentException("version must not be blank");
        if (canonicalDigest == null || !DIGEST.matcher(canonicalDigest).matches()) throw new IllegalArgumentException("canonicalDigest must be lowercase sha256");
    }
}
