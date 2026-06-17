package com.dylan.esquery.service;

import java.time.Instant;
import java.util.Collection;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.stereotype.Repository;

import com.dylan.esquery.api.model.RebuildTask;

/**
 * 重建任务仓库，保存索引重建任务的内存状态。
 */
@Repository
public class RebuildTaskRepository {
	private final Map<String, RebuildTask> tasks = new ConcurrentHashMap<>();

	/**
	 * 创建业务对象。
	 */
	public RebuildTask create(String taskId, String index, String targetIndex, String type) {
		RebuildTask task = new RebuildTask();
		task.setTaskId(taskId);
		task.setIndex(index);
		task.setTargetIndex(targetIndex);
		task.setType(type);
		task.setStatus("SUBMITTED");
		task.setCreatedAt(Instant.now());
		task.setUpdatedAt(task.getCreatedAt());
		tasks.put(taskId, task);
		return task;
	}

	/**
	 * 查找指定业务对象。
	 */
	public RebuildTask findById(String taskId) {
		RebuildTask task = tasks.get(taskId);
		if (task == null) {
			throw new IllegalArgumentException("Rebuild task not found: " + taskId);
		}
		return task;
	}

	/**
	 * 查找指定业务对象。
	 */
	public Collection<RebuildTask> findAll() {
		return tasks.values();
	}

	/**
	 * 处理 markRunning 相关逻辑。
	 */
	public void markRunning(String taskId) {
		RebuildTask task = findById(taskId);
		task.setStatus("RUNNING");
		task.setUpdatedAt(Instant.now());
	}

	/**
	 * 处理 markProgress 相关逻辑。
	 */
	public void markProgress(String taskId, long totalIndexed, String lastCursor) {
		RebuildTask task = findById(taskId);
		task.setTotalIndexed(totalIndexed);
		task.setLastCursor(lastCursor);
		task.setUpdatedAt(Instant.now());
	}

	/**
	 * 处理 markSuccess 相关逻辑。
	 */
	public void markSuccess(String taskId) {
		RebuildTask task = findById(taskId);
		task.setStatus("SUCCESS");
		task.setUpdatedAt(Instant.now());
	}

	/**
	 * 处理 markFailed 相关逻辑。
	 */
	public void markFailed(String taskId, Exception e) {
		RebuildTask task = findById(taskId);
		task.setStatus("FAILED");
		task.setErrorMessage(e.getMessage());
		task.setUpdatedAt(Instant.now());
	}
}
