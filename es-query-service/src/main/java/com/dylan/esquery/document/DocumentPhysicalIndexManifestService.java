package com.dylan.esquery.document;

import java.time.Instant;
import java.util.Optional;

/** Seal/回读端口；实现必须在 seal 后设置 write block。 */
public interface DocumentPhysicalIndexManifestService {
    DocumentPhysicalIndexManifest seal(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease,
                                       DocumentCorpusDefinition corpus, DocumentIndexDefinition schema,
                                       long documentCount, long chunkCount, String indexContentDigest, Instant now);
    DocumentPhysicalIndexManifest requireSealed(IndexBuildTargetHandle handle, Instant deadline);
    Optional<DocumentPhysicalIndexManifest> findSealed(IndexBuildTargetHandle handle, Instant deadline);
}
