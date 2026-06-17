package com.dylan.workflow.model;

import com.dylan.workflow.web.WorkflowActionMessage;

/**
 * 本地内存版 Outbox 事件，后续可平移到数据库表。
 */
public class WorkflowOutboxEvent {
	private String eventId;
	private WorkflowActionMessage message;
	private WorkflowOutboxStatus status = WorkflowOutboxStatus.PENDING;
	private int attempts;
	private String lastError;

	public String getEventId() {
		return eventId;
	}

	public void setEventId(String eventId) {
		this.eventId = eventId;
	}

	public WorkflowActionMessage getMessage() {
		return message;
	}

	public void setMessage(WorkflowActionMessage message) {
		this.message = message;
	}

	public WorkflowOutboxStatus getStatus() {
		return status;
	}

	public void setStatus(WorkflowOutboxStatus status) {
		this.status = status;
	}

	public int getAttempts() {
		return attempts;
	}

	public void setAttempts(int attempts) {
		this.attempts = attempts;
	}

	public String getLastError() {
		return lastError;
	}

	public void setLastError(String lastError) {
		this.lastError = lastError;
	}
}
