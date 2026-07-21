package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildTask;

import java.util.Collection;

/** 索引重建任务仓库端口。 */
public interface RebuildTaskRepository {

	RebuildTask create(String taskId, String index, String targetIndex, String type);

	RebuildTask findById(String taskId);

	Collection<RebuildTask> findAll();

	void markRunning(String taskId);

	void markProgress(String taskId, long totalIndexed, String lastCursor);

	void markSuccess(String taskId);

	void markValidationPassed(String taskId, String digest, String message);

	void markValidationSkipped(String taskId, String message);

	void markValidationFailed(String taskId, String message);

	void markFailed(String taskId, Exception e);
}
