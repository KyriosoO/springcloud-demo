package com.dylan.esquery.document;

import java.time.Instant;
import java.util.List;

/** Index-time chunk embedding seam；vector disabled 时不得调用。 */
public interface DocumentIndexEmbeddingPort {
    List<NormalizedDocumentChunk> embed(List<NormalizedDocumentChunk> chunks, DocumentCorpusDefinition corpus,
                                        DocumentIndexDefinition schema, Instant deadline);
}
