package com.dylan.esquery.document;

import com.dylan.esquery.api.model.SourceSnapshotRef;

/** Connector 对 caller snapshot assertion 的不可变确认。 */
public record SourceSnapshotDescriptor(SourceSnapshotRef snapshotRef, long documentCount) {
    public SourceSnapshotDescriptor {
        if (snapshotRef == null) throw new IllegalArgumentException("snapshotRef must not be null");
        if (documentCount < 0) throw new IllegalArgumentException("documentCount must not be negative");
    }
}
