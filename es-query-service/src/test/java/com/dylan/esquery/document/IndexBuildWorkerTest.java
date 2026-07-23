package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.api.model.SourceSnapshotRef;
import com.dylan.esquery.service.DocumentChunkSchemaValidator;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class IndexBuildWorkerTest {
    private static final Instant NOW = Instant.parse("2026-07-14T00:00:00Z");
    private static final DocumentCorpusKeyDto KEY = new DocumentCorpusKeyDto("policy", "document");
    private static final DocumentSchemaRefDto SCHEMA = new DocumentSchemaRefDto("document", "3", "a".repeat(64));
    private static final SourceSnapshotRef SNAPSHOT = new SourceSnapshotRef("snapshot", "v1", "b".repeat(64));
    private static final DocumentCorpusDefinition CORPUS = new DocumentCorpusDefinition(KEY,
            "agent-doc-policy-document-read", SCHEMA, "standard", "disabled", "char-window-v3", "connector-v1", Set.of());
    private static final DocumentIndexDefinition INDEX_DEFINITION = new DocumentIndexDefinition(
            SCHEMA, "standard", null, null, List.of());

    @Test
    void executesFullSnapshotAndSealsBeforeSuccess() {
        Fixture fixture = new Fixture();
        when(fixture.tasks.tryAcquireNext(eq("worker-1"), eq(NOW), any())).thenReturn(Optional.of(fixture.lease));
        when(fixture.tasks.cancellationRequested(any(), any())).thenReturn(false);
        when(fixture.connector.assertSnapshot(eq(SNAPSHOT), any())).thenReturn(new SourceSnapshotDescriptor(SNAPSHOT, 1));
        when(fixture.manifests.findSealed(any(), any())).thenReturn(Optional.empty());
        when(fixture.connector.readPage(eq(SNAPSHOT), any(), eq(100), any(), any())).thenReturn(
                new DocumentSourcePage(List.of(source()), new ProtectedSourceCursor(null), true));
        when(fixture.writer.open(eq(fixture.lease), eq(INDEX_DEFINITION), any())).thenReturn(fixture.handle);
        when(fixture.tasks.checkpoint(eq(fixture.lease), any(), eq(1L), eq(1L), eq(1L), any(), any()))
                .thenReturn(Optional.of(fixture.checkpoint));
        when(fixture.writer.count(eq(fixture.handle), eq(fixture.checkpoint), any())).thenReturn(1L);
        when(fixture.writer.contentDigest(eq(fixture.handle), eq(fixture.checkpoint), eq(CORPUS), eq(INDEX_DEFINITION), any()))
                .thenReturn("c".repeat(64));
        DocumentPhysicalIndexManifest manifest = manifest();
        when(fixture.manifests.seal(eq(fixture.handle), eq(fixture.checkpoint), eq(CORPUS), eq(INDEX_DEFINITION),
                eq(1L), eq(1L), eq("c".repeat(64)), any())).thenReturn(manifest);
        when(fixture.manifests.requireSealed(eq(fixture.handle), any())).thenReturn(manifest);
        when(fixture.validation.validate(eq(fixture.handle), eq(manifest), any())).thenReturn(
                new IndexTechnicalValidationEvidence(manifest, true, true, true, true, List.of()));
        when(fixture.tasks.markSuccess(eq(fixture.checkpoint), eq("c".repeat(64)), eq("d".repeat(64)), any())).thenReturn(true);

        assertThat(fixture.worker.runNext("worker-1")).isTrue();

        verify(fixture.writer).write(eq(fixture.handle), eq(fixture.lease), any(), any());
        verify(fixture.manifests).requireSealed(eq(fixture.handle), any());
        verify(fixture.tasks).markSuccess(eq(fixture.checkpoint), eq("c".repeat(64)), eq("d".repeat(64)), any());
        verify(fixture.tasks, never()).markFailed(any(), any(), any(), any());
    }

    @Test
    void cancellationAtPageBoundaryDoesNotOpenOrWriteIndex() {
        Fixture fixture = new Fixture();
        when(fixture.tasks.tryAcquireNext(eq("worker-1"), eq(NOW), any())).thenReturn(Optional.of(fixture.lease));
        when(fixture.tasks.cancellationRequested(fixture.lease.taskId(), fixture.lease.leaseOwner())).thenReturn(true);
        when(fixture.connector.assertSnapshot(eq(SNAPSHOT), any())).thenReturn(new SourceSnapshotDescriptor(SNAPSHOT, 1));
        when(fixture.manifests.findSealed(any(), any())).thenReturn(Optional.empty());
        when(fixture.writer.open(eq(fixture.lease), eq(INDEX_DEFINITION), any())).thenReturn(fixture.handle);
        when(fixture.tasks.markCancelled(eq(fixture.lease), any())).thenReturn(true);

        assertThat(fixture.worker.runNext("worker-1")).isTrue();

        verify(fixture.tasks).markCancelled(eq(fixture.lease), any());
        verify(fixture.writer, never()).write(any(), any(), any(), any());
        verify(fixture.tasks, never()).markSuccess(any(), any(), any(), any());
    }

    @Test
    void finalizesPreviouslySealedIndexWithoutReopeningSourceOrWriting() {
        Fixture fixture = new Fixture();
        DocumentRebuildTaskLease sealedLease = lease(2, 1, 1, 1);
        DocumentPhysicalIndexManifest manifest = manifest();
        when(fixture.tasks.tryAcquireNext(eq("worker-1"), eq(NOW), any())).thenReturn(Optional.of(sealedLease));
        when(fixture.manifests.findSealed(any(), any())).thenReturn(Optional.of(manifest));
        when(fixture.validation.validate(any(), eq(manifest), any())).thenReturn(
                new IndexTechnicalValidationEvidence(manifest, true, true, true, true, List.of()));
        when(fixture.tasks.markSuccess(eq(sealedLease), eq("c".repeat(64)), eq("d".repeat(64)), any()))
                .thenReturn(true);

        assertThat(fixture.worker.runNext("worker-1")).isTrue();

        verify(fixture.tasks).markSuccess(eq(sealedLease), eq("c".repeat(64)), eq("d".repeat(64)), any());
        verify(fixture.connector, never()).assertSnapshot(any(), any());
        verify(fixture.connector, never()).readPage(any(), any(), anyInt(), any(), any());
        verify(fixture.writer, never()).open(any(), any(), any());
        verify(fixture.writer, never()).write(any(), any(), any(), any());
        verify(fixture.tasks, never()).markFailed(any(), any(), any(), any());
    }

    private static SourceDocument source() {
        return new SourceDocument("tenant", "doc", "v1", "正文", "标题", null, null, null, NOW,
                "ACTIVE", "acl", "v1", "TENANT", List.of(), List.of(), List.of(), List.of(), List.of(), List.of());
    }

    private static DocumentPhysicalIndexManifest manifest() {
        return new DocumentPhysicalIndexManifest("agent-doc-policy-document-s3-build", KEY, SCHEMA, "standard",
                "disabled", "char-window-v3", "snapshot:v1", SNAPSHOT.canonicalDigest(), "task-1", 1, 1,
                "c".repeat(64), NOW, "d".repeat(64));
    }

    private static final class Fixture {
        final DocumentRebuildTaskRepository tasks = mock(DocumentRebuildTaskRepository.class);
        final DocumentSourceConnector connector = mock(DocumentSourceConnector.class);
        final IndexBuildWriter writer = mock(IndexBuildWriter.class);
        final DocumentPhysicalIndexManifestService manifests = mock(DocumentPhysicalIndexManifestService.class);
        final IndexTechnicalValidationPort validation = mock(IndexTechnicalValidationPort.class);
        final DocumentRebuildTaskLease lease = lease(1, 0, 0, 0);
        final DocumentRebuildTaskLease checkpoint = lease(2, 1, 1, 1);
        final IndexBuildTargetHandle handle = new IndexBuildTargetHandle("task-1", "agent-doc-policy-document-s3-build");
        final IndexBuildWorker worker;

        Fixture() {
            when(connector.connectorId()).thenReturn("connector-v1");
            DocumentIndexEmbeddingPort embeddings = (chunks, corpus, schema, deadline) -> chunks;
            worker = new IndexBuildWorker(tasks, new DocumentCorpusCatalog(List.of(CORPUS)),
                    new DocumentSourceConnectorRegistry(List.of(connector)),
                    new DocumentIndexDefinitionRegistry(List.of(INDEX_DEFINITION)), new DocumentNormalizer(1000),
                    new DocumentChunker(100, 0), embeddings, new DocumentChunkSchemaValidator(),
                    new DocumentChunkDocumentMapper(), writer, manifests, validation,
                    new DocumentRebuildWorkerPolicy(100, 2, Duration.ofSeconds(30), Duration.ofMinutes(10)),
                    Clock.fixed(NOW, ZoneOffset.UTC));
        }
    }

    private static DocumentRebuildTaskLease lease(long version, long documents, long chunks, long attempts) {
        return new DocumentRebuildTaskLease("task-1", KEY, "connector-v1", SNAPSHOT, SCHEMA,
                "agent-doc-policy-document-s3-build", 1L, new ProtectedSourceCursor(null), documents, chunks,
                attempts, version, "worker-1", NOW.plusSeconds(30));
    }
}
