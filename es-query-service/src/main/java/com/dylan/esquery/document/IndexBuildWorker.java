package com.dylan.esquery.document;

import com.dylan.esquery.service.DocumentChunkSchemaValidator;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/** FULL_SNAPSHOT rebuild worker；lease loser、snapshot drift 与 partial bulk 均 fail closed。 */
public final class IndexBuildWorker {
    private final DocumentRebuildTaskRepository tasks;
    private final DocumentCorpusCatalog catalog;
    private final DocumentSourceConnectorRegistry connectors;
    private final DocumentIndexDefinitionRegistry schemas;
    private final DocumentNormalizer normalizer;
    private final DocumentChunker chunker;
    private final DocumentIndexEmbeddingPort embeddings;
    private final DocumentChunkSchemaValidator chunkValidator;
    private final DocumentChunkDocumentMapper chunkMapper;
    private final IndexBuildWriter writer;
    private final DocumentPhysicalIndexManifestService manifests;
    private final IndexTechnicalValidationPort technicalValidation;
    private final DocumentRebuildWorkerPolicy policy;
    private final Clock clock;

    public IndexBuildWorker(DocumentRebuildTaskRepository tasks, DocumentCorpusCatalog catalog,
                            DocumentSourceConnectorRegistry connectors, DocumentIndexDefinitionRegistry schemas,
                            DocumentNormalizer normalizer, DocumentChunker chunker, DocumentIndexEmbeddingPort embeddings,
                            DocumentChunkSchemaValidator chunkValidator, DocumentChunkDocumentMapper chunkMapper,
                            IndexBuildWriter writer, DocumentPhysicalIndexManifestService manifests,
                            IndexTechnicalValidationPort technicalValidation, DocumentRebuildWorkerPolicy policy, Clock clock) {
        this.tasks = tasks; this.catalog = catalog; this.connectors = connectors; this.schemas = schemas;
        this.normalizer = normalizer; this.chunker = chunker; this.embeddings = embeddings;
        this.chunkValidator = chunkValidator; this.chunkMapper = chunkMapper; this.writer = writer;
        this.manifests = manifests; this.technicalValidation = technicalValidation; this.policy = policy; this.clock = clock;
    }

    public boolean runNext(String leaseOwner) {
        Instant now = clock.instant();
        Optional<DocumentRebuildTaskLease> acquired = tasks.tryAcquireNext(leaseOwner, now, policy.leaseDuration());
        if (acquired.isEmpty()) return false;
        execute(acquired.get(), now.plus(policy.taskTimeout()));
        return true;
    }

    private void execute(DocumentRebuildTaskLease initialLease, Instant deadline) {
        DocumentRebuildTaskLease lease = initialLease;
        try {
            DocumentCorpusDefinition corpus = catalog.require(lease.corpusKey());
            if (!corpus.sourceConnectorId().equals(lease.connectorId()) || !corpus.schemaRef().equals(lease.schemaRef())) {
                throw new DocumentRebuildFailure("CATALOG_BINDING_DRIFT");
            }
            schemas.requireCorpusClosure(corpus);
            DocumentIndexDefinition schema = schemas.require(lease.schemaRef());
            IndexBuildTargetHandle recoveryHandle = new IndexBuildTargetHandle(
                    lease.taskId(), lease.targetPhysicalIndexSafeRef());
            Optional<DocumentPhysicalIndexManifest> sealed = manifests.findSealed(recoveryHandle, deadline);
            if (sealed.isPresent()) {
                completeSealedRecovery(lease, recoveryHandle, corpus, schema, sealed.get(), deadline);
                return;
            }
            DocumentSourceConnector connector = connectors.require(lease.connectorId());
            SourceSnapshotDescriptor asserted = connector.assertSnapshot(lease.sourceSnapshotRef(), deadline);
            requireSnapshot(asserted, lease);
            IndexBuildTargetHandle handle = writer.open(lease, schema, deadline);
            ProtectedSourceCursor cursor = lease.cursor();
            long documentsRead = lease.documentsRead();
            long chunksIndexed = lease.chunksIndexed();
            long bulkAttempts = lease.bulkAttempts();
            String lastKey = null;
            Map<String, String> aclDigests = new HashMap<>();
            boolean complete = false;
            while (!complete) {
                requireBeforeDeadline(deadline);
                if (tasks.cancellationRequested(lease.taskId(), lease.leaseOwner())) {
                    requireTerminal(tasks.markCancelled(lease, clock.instant()));
                    return;
                }
                DocumentRebuildTaskLease pageLease = lease;
                DocumentSourcePage page = connector.readPage(lease.sourceSnapshotRef(), cursor, policy.pageSize(), deadline,
                        () -> tasks.cancellationRequested(pageLease.taskId(), pageLease.leaseOwner()));
                List<NormalizedDocumentChunk> batch = new ArrayList<>();
                for (SourceDocument source : page.documents()) {
                    String key = source.tenantId() + "\u001f" + source.documentId() + "\u001f" + source.documentVersion();
                    if (lastKey != null && key.compareTo(lastKey) <= 0) throw new DocumentRebuildFailure("SOURCE_ORDER_UNSTABLE");
                    lastKey = key;
                    NormalizedDocument document = normalizer.normalize(source, corpus);
                    verifyAclConsistency(document, aclDigests);
                    batch.addAll(chunker.chunk(document, corpus.chunkStrategyRef()));
                    documentsRead++;
                }
                if (schema.vectorEnabled() && !batch.isEmpty()) batch = new ArrayList<>(embeddings.embed(List.copyOf(batch), corpus, schema, deadline));
                for (NormalizedDocumentChunk chunk : batch) chunkValidator.validate(corpus, schema, chunkMapper.toDocument(chunk));
                if (!batch.isEmpty()) {
                    RuntimeException lastFailure = null;
                    for (int attempt = 1; attempt <= policy.maxBulkAttempts(); attempt++) {
                        bulkAttempts++;
                        try {
                            writer.write(handle, lease, List.copyOf(batch), deadline);
                            lastFailure = null;
                            break;
                        } catch (RuntimeException failure) {
                            lastFailure = failure;
                        }
                    }
                    if (lastFailure != null) throw new DocumentRebuildFailure("BULK_OUTCOME_UNRESOLVED", lastFailure);
                    chunksIndexed += batch.size();
                }
                cursor = page.nextCursor();
                complete = page.complete();
                lease = tasks.checkpoint(lease, cursor, documentsRead, chunksIndexed, bulkAttempts,
                        clock.instant(), policy.leaseDuration()).orElseThrow(() -> new LeaseLostException());
            }
            SourceSnapshotDescriptor reaffirmed = connector.assertSnapshot(lease.sourceSnapshotRef(), deadline);
            requireSnapshot(reaffirmed, lease);
            if (lease.expectedDocumentCount() != null && lease.expectedDocumentCount() != documentsRead) {
                throw new DocumentRebuildFailure("DOCUMENT_COUNT_MISMATCH");
            }
            writer.refresh(handle, lease, deadline);
            long actualChunks = writer.count(handle, lease, deadline);
            if (actualChunks != chunksIndexed) throw new DocumentRebuildFailure("CHUNK_COUNT_MISMATCH");
            String contentDigest = writer.contentDigest(handle, lease, corpus, schema, deadline);
            DocumentPhysicalIndexManifest manifest = manifests.seal(handle, lease, corpus, schema,
                    documentsRead, chunksIndexed, contentDigest, clock.instant());
            DocumentPhysicalIndexManifest reread = manifests.requireSealed(handle, deadline);
            if (!manifest.equals(reread)) throw new DocumentRebuildFailure("MANIFEST_READBACK_MISMATCH");
            IndexTechnicalValidationEvidence evidence = technicalValidation.validate(handle, manifest, deadline);
            if (!evidence.passed()) throw new DocumentRebuildFailure("TECHNICAL_VALIDATION_FAILED");
            requireTerminal(tasks.markSuccess(lease, contentDigest, manifest.manifestDigest(), clock.instant()));
        } catch (LeaseLostException ignored) {
            // 新 owner 已取得事实权威；旧 worker 立即停止且不得写终态。
        } catch (DocumentRebuildFailure failure) {
            tasks.markFailed(lease, failure.failureCode(), diagnosticId(), clock.instant());
        } catch (RuntimeException failure) {
            tasks.markFailed(lease, "UNCLASSIFIED_REBUILD_FAILURE", diagnosticId(), clock.instant());
        }
    }

    private static void requireSnapshot(SourceSnapshotDescriptor descriptor, DocumentRebuildTaskLease lease) {
        if (descriptor == null || !lease.sourceSnapshotRef().equals(descriptor.snapshotRef())) {
            throw new DocumentRebuildFailure("SOURCE_SNAPSHOT_DRIFT");
        }
        if (lease.expectedDocumentCount() != null && descriptor.documentCount() != lease.expectedDocumentCount()) {
            throw new DocumentRebuildFailure("SOURCE_COUNT_ASSERTION_CONFLICT");
        }
    }

    private void completeSealedRecovery(DocumentRebuildTaskLease lease,
                                        IndexBuildTargetHandle handle,
                                        DocumentCorpusDefinition corpus,
                                        DocumentIndexDefinition schema,
                                        DocumentPhysicalIndexManifest manifest,
                                        Instant deadline) {
        String expectedSourceRef = lease.sourceSnapshotRef().snapshotId() + ":" + lease.sourceSnapshotRef().version();
        if (!handle.physicalIndex().equals(manifest.physicalIndex())
                || !lease.taskId().equals(manifest.taskId())
                || !corpus.corpusKey().equals(manifest.corpusKey())
                || !schema.schemaRef().equals(manifest.schemaRef())
                || !corpus.analyzerRef().equals(manifest.analyzerRef())
                || !corpus.vectorPolicyRef().equals(manifest.vectorPolicyRef())
                || !corpus.chunkStrategyRef().equals(manifest.chunkStrategyRef())
                || !expectedSourceRef.equals(manifest.sourceSnapshotRef())
                || !lease.sourceSnapshotRef().canonicalDigest().equals(manifest.sourceSnapshotDigest())
                || lease.documentsRead() != manifest.documentCount()
                || lease.chunksIndexed() != manifest.chunkCount()
                || lease.expectedDocumentCount() != null
                && lease.expectedDocumentCount() != manifest.documentCount()) {
            throw new DocumentRebuildFailure("SEALED_RECOVERY_BINDING_MISMATCH");
        }
        IndexTechnicalValidationEvidence evidence = technicalValidation.validate(handle, manifest, deadline);
        if (!evidence.passed()) throw new DocumentRebuildFailure("TECHNICAL_VALIDATION_FAILED");
        requireTerminal(tasks.markSuccess(lease, manifest.indexContentDigest(), manifest.manifestDigest(), clock.instant()));
    }

    private static void verifyAclConsistency(NormalizedDocument document, Map<String, String> digests) {
        String key = document.tenantId() + "\u001f" + document.documentId() + "\u001f" + document.documentVersion();
        String digest = String.join("\u001f", document.aclRef(), document.aclVersion(), document.visibility(),
                String.join("\u001e", document.userIds()), String.join("\u001e", document.departmentIds()),
                String.join("\u001e", document.roleIds()), String.join("\u001e", document.attributeKeys()));
        String previous = digests.putIfAbsent(key, digest);
        if (previous != null && !previous.equals(digest)) throw new DocumentRebuildFailure("DOCUMENT_ACL_DRIFT");
    }

    private void requireBeforeDeadline(Instant deadline) {
        if (!clock.instant().isBefore(deadline)) throw new DocumentRebuildFailure("REBUILD_DEADLINE_EXCEEDED");
    }
    private static void requireTerminal(boolean changed) { if (!changed) throw new LeaseLostException(); }
    private static String diagnosticId() { return "diag-" + UUID.randomUUID().toString().substring(0, 12); }
    private static final class LeaseLostException extends RuntimeException { }
}
