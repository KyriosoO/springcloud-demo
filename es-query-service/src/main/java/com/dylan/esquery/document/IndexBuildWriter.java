package com.dylan.esquery.document;

import java.time.Instant;
import java.util.List;

/** Document rebuild 的唯一写端口；不接受裸 index 字符串。 */
public interface IndexBuildWriter {
    IndexBuildTargetHandle open(DocumentRebuildTaskLease lease, DocumentIndexDefinition definition, Instant deadline);
    void write(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease,
               List<NormalizedDocumentChunk> chunks, Instant deadline);
    void refresh(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease, Instant deadline);
    long count(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease, Instant deadline);
    String contentDigest(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease,
                         DocumentCorpusDefinition corpus, DocumentIndexDefinition schema, Instant deadline);
}
