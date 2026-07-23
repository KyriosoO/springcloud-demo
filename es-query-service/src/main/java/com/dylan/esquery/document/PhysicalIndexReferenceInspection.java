package com.dylan.esquery.document;

import java.util.List;

public record PhysicalIndexReferenceInspection(
        String physicalIndex,
        List<String> aliasRefs,
        boolean unfinishedTaskRef,
        String manifestDigest,
        String attestationDigest) {
    public PhysicalIndexReferenceInspection { aliasRefs = List.copyOf(aliasRefs == null ? List.of() : aliasRefs); }
    public boolean deletionSafe() { return aliasRefs.isEmpty() && !unfinishedTaskRef; }
}
