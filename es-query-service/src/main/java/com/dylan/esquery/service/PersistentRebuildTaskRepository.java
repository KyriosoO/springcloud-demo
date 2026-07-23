package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;
import org.springframework.context.annotation.Primary;
import org.springframework.stereotype.Repository;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

/** 使用数据库持久化索引重建任务状态，避免服务重启后丢失 validation digest。 */
@Primary
@Repository
public class PersistentRebuildTaskRepository implements RebuildTaskRepository {

	private final DataSource dataSource;

	public PersistentRebuildTaskRepository(DataSource dataSource) {
		this.dataSource = dataSource;
	}

	public RebuildTask create(String taskId, String index, String targetIndex, String type) {
		RebuildTask task = new RebuildTask();
		Instant now = Instant.now();
		task.setTaskId(taskId);
		task.setIndex(index);
		task.setTargetIndex(targetIndex);
		task.setType(type);
		task.setStatus("PENDING");
		task.setCreatedAt(now);
		task.setUpdatedAt(now);
		executeUpdate("""
				insert into document_rebuild_task
				(task_id, index_name, target_index, type, status, total_indexed, created_at, updated_at)
				values (?, ?, ?, ?, ?, ?, ?, ?)
				""", ps -> {
			ps.setString(1, task.getTaskId());
			ps.setString(2, task.getIndex());
			ps.setString(3, task.getTargetIndex());
			ps.setString(4, task.getType());
			ps.setString(5, task.getStatus());
			ps.setLong(6, task.getTotalIndexed());
			ps.setTimestamp(7, timestamp(task.getCreatedAt()));
			ps.setTimestamp(8, timestamp(task.getUpdatedAt()));
		});
		return task;
	}

	public RebuildTask findById(String taskId) {
		try (Connection connection = dataSource.getConnection();
				PreparedStatement ps = connection.prepareStatement("""
						select task_id, index_name, target_index, type, status, total_indexed, last_cursor,
						       error_message, validation_status, validation_digest, validated_at,
						       validation_message, created_at, updated_at
						from document_rebuild_task
						where task_id = ?
						""")) {
			ps.setString(1, taskId);
			try (ResultSet rs = ps.executeQuery()) {
				if (rs.next()) {
					return map(rs);
				}
			}
		} catch (SQLException ex) {
			throw new IllegalStateException("Failed to query rebuild task: " + taskId, ex);
		}
		throw new IllegalArgumentException("Rebuild task not found: " + taskId);
	}

	public Collection<RebuildTask> findAll() {
		List<RebuildTask> tasks = new ArrayList<>();
		try (Connection connection = dataSource.getConnection();
				PreparedStatement ps = connection.prepareStatement("""
						select task_id, index_name, target_index, type, status, total_indexed, last_cursor,
						       error_message, validation_status, validation_digest, validated_at,
						       validation_message, created_at, updated_at
						from document_rebuild_task
						order by created_at desc, task_id desc
						""");
				ResultSet rs = ps.executeQuery()) {
			while (rs.next()) {
				tasks.add(map(rs));
			}
			return tasks;
		} catch (SQLException ex) {
			throw new IllegalStateException("Failed to query rebuild tasks", ex);
		}
	}

	public void markRunning(String taskId) {
		updateTask(taskId, task -> task.setStatus("RUNNING"));
	}

	public void markProgress(String taskId, long totalIndexed, String lastCursor) {
		updateTask(taskId, task -> {
			task.setTotalIndexed(totalIndexed);
			task.setLastCursor(lastCursor);
		});
	}

	public void markSuccess(String taskId) {
		updateTask(taskId, task -> task.setStatus("SUCCESS"));
	}

	public void markValidationPassed(String taskId, String digest, String message) {
		updateTask(taskId, task -> {
			Instant now = Instant.now();
			task.setValidationStatus("PASSED");
			task.setValidationDigest(digest);
			task.setValidatedAt(now);
			task.setValidationMessage(message);
		});
	}

	public void markValidationSkipped(String taskId, String message) {
		updateTask(taskId, task -> {
			Instant now = Instant.now();
			task.setValidationStatus("SKIPPED");
			task.setValidationDigest(null);
			task.setValidatedAt(now);
			task.setValidationMessage(message);
		});
	}

	public void markValidationFailed(String taskId, String message) {
		updateTask(taskId, task -> {
			Instant now = Instant.now();
			task.setValidationStatus("FAILED");
			task.setValidationDigest(null);
			task.setValidatedAt(now);
			task.setValidationMessage(message);
		});
	}

	public void markFailed(String taskId, Exception e) {
		updateTask(taskId, task -> {
			Instant now = Instant.now();
			task.setStatus("FAILED");
			task.setErrorMessage(e.getMessage());
			task.setValidationStatus("FAILED");
			task.setValidationDigest(null);
			task.setValidatedAt(now);
			task.setValidationMessage(e.getMessage());
		});
	}

	private void updateTask(String taskId, TaskMutator mutator) {
		RebuildTask task = findById(taskId);
		mutator.apply(task);
		task.setUpdatedAt(Instant.now());
		executeUpdate("""
				update document_rebuild_task
				set status = ?, total_indexed = ?, last_cursor = ?, error_message = ?,
				    validation_status = ?, validation_digest = ?, validated_at = ?,
				    validation_message = ?, updated_at = ?
				where task_id = ?
				""", ps -> {
			ps.setString(1, task.getStatus());
			ps.setLong(2, task.getTotalIndexed());
			ps.setString(3, task.getLastCursor());
			ps.setString(4, task.getErrorMessage());
			ps.setString(5, task.getValidationStatus());
			ps.setString(6, task.getValidationDigest());
			ps.setTimestamp(7, timestamp(task.getValidatedAt()));
			ps.setString(8, task.getValidationMessage());
			ps.setTimestamp(9, timestamp(task.getUpdatedAt()));
			ps.setString(10, task.getTaskId());
		});
	}

	private void executeUpdate(String sql, SqlBinder binder) {
		try (Connection connection = dataSource.getConnection();
				PreparedStatement ps = connection.prepareStatement(sql)) {
			binder.bind(ps);
			ps.executeUpdate();
		} catch (SQLException ex) {
			throw new IllegalStateException("Failed to update rebuild task repository", ex);
		}
	}

	private RebuildTask map(ResultSet rs) throws SQLException {
		RebuildTask task = new RebuildTask();
		task.setTaskId(rs.getString("task_id"));
		task.setIndex(rs.getString("index_name"));
		task.setTargetIndex(rs.getString("target_index"));
		task.setType(rs.getString("type"));
		task.setStatus(rs.getString("status"));
		task.setTotalIndexed(rs.getLong("total_indexed"));
		task.setLastCursor(rs.getString("last_cursor"));
		task.setErrorMessage(rs.getString("error_message"));
		task.setValidationStatus(rs.getString("validation_status"));
		task.setValidationDigest(rs.getString("validation_digest"));
		task.setValidatedAt(instant(rs.getTimestamp("validated_at")));
		task.setValidationMessage(rs.getString("validation_message"));
		task.setCreatedAt(instant(rs.getTimestamp("created_at")));
		task.setUpdatedAt(instant(rs.getTimestamp("updated_at")));
		return task;
	}

	private static Timestamp timestamp(Instant instant) {
		return instant == null ? null : Timestamp.from(instant);
	}

	private static Instant instant(Timestamp timestamp) {
		return timestamp == null ? null : timestamp.toInstant();
	}

	private interface TaskMutator {
		void apply(RebuildTask task);
	}

	private interface SqlBinder {
		void bind(PreparedStatement ps) throws SQLException;
	}
}
