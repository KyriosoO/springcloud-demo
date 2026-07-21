package com.dylan.esquery.api.model;

/** 不暴露 alias/physical index 的 Document read target 完整性绑定。 */
public record DocumentTargetBindingDto(
        String schemaVersion,
        String indexContentDigest,
        String manifestDigest,
        String attestationDigest) {
    public DocumentTargetBindingDto {
        if (schemaVersion == null || schemaVersion.isBlank()) {
            throw new IllegalArgumentException("schemaVersion must not be blank");
        }
        requireDigest(indexContentDigest, "indexContentDigest");
        requireDigest(manifestDigest, "manifestDigest");
        requireDigest(attestationDigest, "attestationDigest");
    }

    private static void requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be lowercase SHA-256 hex");
        }
    }
}
