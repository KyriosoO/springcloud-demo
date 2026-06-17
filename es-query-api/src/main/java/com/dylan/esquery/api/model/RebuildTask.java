package com.dylan.esquery.api.model;

import java.time.Instant;

/**
 * 索引重建任务，记录重建进度、状态和错误信息。
 */
public class RebuildTask {
	private String taskId;
	private String index;
	private String targetIndex;
	private String type;
	private String status;
	private long totalIndexed;
	private String lastCursor;
	private String errorMessage;
	private Instant createdAt;
	private Instant updatedAt;

	public String getTaskId() { return taskId; }
	public void setTaskId(String taskId) { this.taskId = taskId; }
	public String getIndex() { return index; }
	public void setIndex(String index) { this.index = index; }
	public String getTargetIndex() { return targetIndex; }
	public void setTargetIndex(String targetIndex) { this.targetIndex = targetIndex; }
	public String getType() { return type; }
	public void setType(String type) { this.type = type; }
	public String getStatus() { return status; }
	public void setStatus(String status) { this.status = status; }
	public long getTotalIndexed() { return totalIndexed; }
	public void setTotalIndexed(long totalIndexed) { this.totalIndexed = totalIndexed; }
	public String getLastCursor() { return lastCursor; }
	public void setLastCursor(String lastCursor) { this.lastCursor = lastCursor; }
	public String getErrorMessage() { return errorMessage; }
	public void setErrorMessage(String errorMessage) { this.errorMessage = errorMessage; }
	public Instant getCreatedAt() { return createdAt; }
	public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
	public Instant getUpdatedAt() { return updatedAt; }
	public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
