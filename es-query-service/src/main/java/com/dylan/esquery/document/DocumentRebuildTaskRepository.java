package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentRebuildTaskView;
import com.dylan.esquery.api.model.StartDocumentRebuildRequest;

import java.time.Duration;
import java.time.Instant;
import java.util.Optional;

public interface DocumentRebuildTaskRepository {
    DocumentRebuildTaskView createOrGet(DocumentCorpusDefinition definition, StartDocumentRebuildRequest request,
                                        String targetSafeRef, String idempotencyDigest, String requestDigest);
    DocumentRebuildTaskView require(String taskId);
    boolean requestCancellation(String taskId, long expectedRowVersion);
    Optional<DocumentRebuildTaskLease> tryAcquireNext(String leaseOwner, Instant now, Duration leaseDuration);
    boolean cancellationRequested(String taskId, String leaseOwner);
    Optional<DocumentRebuildTaskLease> checkpoint(DocumentRebuildTaskLease lease, ProtectedSourceCursor cursor,
                                                  long documentsRead, long chunksIndexed, long bulkAttempts,
                                                  Instant now, Duration leaseDuration);
    boolean markSuccess(DocumentRebuildTaskLease lease, String contentDigest, String manifestDigest, Instant now);
    boolean markFailed(DocumentRebuildTaskLease lease, String failureCode, String diagnosticId, Instant now);
    boolean markCancelled(DocumentRebuildTaskLease lease, Instant now);
}
