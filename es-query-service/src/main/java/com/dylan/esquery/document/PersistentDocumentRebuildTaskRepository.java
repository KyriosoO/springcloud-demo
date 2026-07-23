package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentRebuildStatus;
import com.dylan.esquery.api.model.DocumentRebuildTaskView;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.api.model.SourceSnapshotRef;
import com.dylan.esquery.api.model.StartDocumentRebuildRequest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;

/** 专用 task 持久化；幂等、lease、checkpoint 与终态均使用数据库 CAS。 */
public final class PersistentDocumentRebuildTaskRepository implements DocumentRebuildTaskRepository {
    private final JdbcTemplate jdbc;

    public PersistentDocumentRebuildTaskRepository(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @Override
    public DocumentRebuildTaskView createOrGet(DocumentCorpusDefinition definition, StartDocumentRebuildRequest request,
                                               String targetSafeRef, String idempotencyDigest, String requestDigest) {
        DocumentCorpusKeyDto key = definition.corpusKey();
        String taskId = UUID.randomUUID().toString();
        Instant now = Instant.now();
        try {
            jdbc.update("INSERT INTO document_index_rebuild_task(task_id,domain_name,material_type,idempotency_digest,request_digest,source_connector_id,source_snapshot_id,source_snapshot_version,source_snapshot_digest,schema_name,schema_version,schema_digest,target_physical_index_safe_ref,status,expected_document_count,documents_read,chunks_indexed,bulk_attempts,cancel_requested,row_version,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    taskId, key.domain(), key.materialType(), idempotencyDigest, requestDigest, definition.sourceConnectorId(),
                    request.sourceSnapshotRef().snapshotId(), request.sourceSnapshotRef().version(), request.sourceSnapshotRef().canonicalDigest(),
                    request.expectedSchemaRef().name(), request.expectedSchemaRef().version(), request.expectedSchemaRef().canonicalDigest(), targetSafeRef,
                    DocumentRebuildStatus.PENDING.name(), request.expectedDocumentCount(), 0L, 0L, 0L, false, 0L, now, now);
            return require(taskId);
        } catch (DuplicateKeyException duplicate) {
            var rows = jdbc.query("SELECT task_id,request_digest FROM document_index_rebuild_task WHERE idempotency_digest=?",
                    (rs, i) -> new String[]{rs.getString(1), rs.getString(2)}, idempotencyDigest);
            if (rows.size() != 1 || !requestDigest.equals(rows.getFirst()[1])) throw new IllegalStateException("IDEMPOTENCY_CONFLICT");
            return require(rows.getFirst()[0]);
        }
    }

    @Override
    public DocumentRebuildTaskView require(String taskId) {
        return jdbc.queryForObject("SELECT task_id,domain_name,material_type,target_physical_index_safe_ref,status,documents_read,chunks_indexed,failure_code,diagnostic_id,created_at,updated_at FROM document_index_rebuild_task WHERE task_id=?",
                (rs, i) -> new DocumentRebuildTaskView(rs.getString(1), new DocumentCorpusKeyDto(rs.getString(2), rs.getString(3)),
                        rs.getString(4), DocumentRebuildStatus.valueOf(rs.getString(5)), rs.getLong(6), rs.getLong(7),
                        rs.getString(8), rs.getString(9), rs.getTimestamp(10).toInstant(), rs.getTimestamp(11).toInstant()), taskId);
    }

    @Override
    public boolean requestCancellation(String taskId, long expectedRowVersion) {
        return jdbc.update("UPDATE document_index_rebuild_task SET cancel_requested=TRUE,row_version=row_version+1,updated_at=CURRENT_TIMESTAMP WHERE task_id=? AND row_version=? AND status IN ('PENDING','RUNNING')",
                taskId, expectedRowVersion) == 1;
    }

    @Override
    public Optional<DocumentRebuildTaskLease> tryAcquireNext(String leaseOwner, Instant now, Duration leaseDuration) {
        if (leaseOwner == null || leaseOwner.isBlank() || leaseDuration == null || leaseDuration.isNegative() || leaseDuration.isZero()) {
            throw new IllegalArgumentException("worker lease parameters invalid");
        }
        var candidates = jdbc.query("SELECT task_id,row_version FROM document_index_rebuild_task WHERE status='PENDING' OR (status='RUNNING' AND lease_expires_at<?) ORDER BY created_at,task_id LIMIT 1",
                (rs, i) -> new Object[]{rs.getString(1), rs.getLong(2)}, now);
        if (candidates.isEmpty()) return Optional.empty();
        String taskId = (String) candidates.getFirst()[0];
        long rowVersion = (long) candidates.getFirst()[1];
        Instant expiresAt = now.plus(leaseDuration);
        int updated = jdbc.update("UPDATE document_index_rebuild_task SET status='RUNNING',lease_owner=?,lease_expires_at=?,started_at=COALESCE(started_at,?),heartbeat_at=?,updated_at=?,row_version=row_version+1 WHERE task_id=? AND row_version=? AND (status='PENDING' OR (status='RUNNING' AND lease_expires_at<?))",
                leaseOwner, expiresAt, now, now, now, taskId, rowVersion, now);
        return updated == 1 ? Optional.of(loadLease(taskId, leaseOwner)) : Optional.empty();
    }

    @Override
    public boolean cancellationRequested(String taskId, String leaseOwner) {
        Boolean value = jdbc.queryForObject("SELECT cancel_requested FROM document_index_rebuild_task WHERE task_id=? AND lease_owner=? AND status='RUNNING'",
                Boolean.class, taskId, leaseOwner);
        return Boolean.TRUE.equals(value);
    }

    @Override
    public Optional<DocumentRebuildTaskLease> checkpoint(DocumentRebuildTaskLease lease, ProtectedSourceCursor cursor,
                                                         long documentsRead, long chunksIndexed, long bulkAttempts,
                                                         Instant now, Duration leaseDuration) {
        if (documentsRead < lease.documentsRead() || chunksIndexed < lease.chunksIndexed() || bulkAttempts < lease.bulkAttempts()) {
            throw new IllegalArgumentException("document rebuild progress must be monotonic");
        }
        int updated = jdbc.update("UPDATE document_index_rebuild_task SET protected_cursor=?,documents_read=?,chunks_indexed=?,bulk_attempts=?,heartbeat_at=?,lease_expires_at=?,updated_at=?,row_version=row_version+1 WHERE task_id=? AND lease_owner=? AND row_version=? AND status='RUNNING'",
                cursor == null || cursor.isInitial() ? null : cursor.ciphertext(), documentsRead, chunksIndexed, bulkAttempts,
                now, now.plus(leaseDuration), now, lease.taskId(), lease.leaseOwner(), lease.rowVersion());
        return updated == 1 ? Optional.of(loadLease(lease.taskId(), lease.leaseOwner())) : Optional.empty();
    }

    @Override public boolean markSuccess(DocumentRebuildTaskLease lease, String contentDigest, String manifestDigest, Instant now) {
        return terminal(lease, "SUCCESS", null, null, contentDigest, manifestDigest, now);
    }
    @Override public boolean markFailed(DocumentRebuildTaskLease lease, String failureCode, String diagnosticId, Instant now) {
        return terminal(lease, "FAILED", failureCode, diagnosticId, null, null, now);
    }
    @Override public boolean markCancelled(DocumentRebuildTaskLease lease, Instant now) {
        return terminal(lease, "CANCELLED", null, null, null, null, now);
    }

    private boolean terminal(DocumentRebuildTaskLease lease, String status, String failureCode, String diagnosticId,
                             String contentDigest, String manifestDigest, Instant now) {
        return jdbc.update("UPDATE document_index_rebuild_task SET status=?,failure_code=?,diagnostic_id=?,content_digest=?,manifest_digest=?,lease_owner=NULL,lease_expires_at=NULL,completed_at=?,updated_at=?,row_version=row_version+1 WHERE task_id=? AND lease_owner=? AND row_version=? AND status='RUNNING'",
                status, failureCode, diagnosticId, contentDigest, manifestDigest, now, now,
                lease.taskId(), lease.leaseOwner(), lease.rowVersion()) == 1;
    }

    private DocumentRebuildTaskLease loadLease(String taskId, String leaseOwner) {
        return jdbc.queryForObject("SELECT task_id,domain_name,material_type,source_connector_id,source_snapshot_id,source_snapshot_version,source_snapshot_digest,schema_name,schema_version,schema_digest,target_physical_index_safe_ref,expected_document_count,protected_cursor,documents_read,chunks_indexed,bulk_attempts,row_version,lease_owner,lease_expires_at FROM document_index_rebuild_task WHERE task_id=? AND lease_owner=? AND status='RUNNING'",
                (rs, i) -> mapLease(rs), taskId, leaseOwner);
    }

    private static DocumentRebuildTaskLease mapLease(ResultSet rs) throws SQLException {
        long expected = rs.getLong(12);
        boolean expectedMissing = rs.wasNull();
        byte[] cursor = rs.getBytes(13);
        return new DocumentRebuildTaskLease(rs.getString(1), new DocumentCorpusKeyDto(rs.getString(2), rs.getString(3)), rs.getString(4),
                new SourceSnapshotRef(rs.getString(5), rs.getString(6), rs.getString(7)),
                new DocumentSchemaRefDto(rs.getString(8), rs.getString(9), rs.getString(10)), rs.getString(11),
                expectedMissing ? null : expected, new ProtectedSourceCursor(cursor), rs.getLong(14), rs.getLong(15),
                rs.getLong(16), rs.getLong(17), rs.getString(18), rs.getTimestamp(19).toInstant());
    }
}
