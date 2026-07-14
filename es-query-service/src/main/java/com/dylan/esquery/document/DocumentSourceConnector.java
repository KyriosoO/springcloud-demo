package com.dylan.esquery.document;

import com.dylan.esquery.api.model.SourceSnapshotRef;

import java.time.Instant;

/** 注册式权威源端口；实现自行持有 endpoint 与 credential。 */
public interface DocumentSourceConnector {
    String connectorId();
    SourceSnapshotDescriptor assertSnapshot(SourceSnapshotRef ref, Instant deadline);
    DocumentSourcePage readPage(SourceSnapshotRef ref, ProtectedSourceCursor cursor, int pageSize,
                                Instant deadline, RebuildCancellationSignal cancellation);
}
