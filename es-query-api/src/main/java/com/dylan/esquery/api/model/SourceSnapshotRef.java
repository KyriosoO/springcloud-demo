package com.dylan.esquery.api.model;

import java.util.regex.Pattern;

/** Connector 可验证的不可变 source snapshot 安全引用。 */
public record SourceSnapshotRef(String snapshotId, String version, String canonicalDigest) {
    private static final Pattern DIGEST = Pattern.compile("[0-9a-f]{64}");
    public SourceSnapshotRef {
        if (snapshotId == null || snapshotId.isBlank()) throw new IllegalArgumentException("snapshotId must not be blank");
        if (version == null || version.isBlank()) throw new IllegalArgumentException("version must not be blank");
        if (canonicalDigest == null || !DIGEST.matcher(canonicalDigest).matches()) throw new IllegalArgumentException("canonicalDigest must be lowercase sha256");
    }
}
