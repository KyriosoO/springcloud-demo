package com.dylan.employee.model;

import com.dylan.workflow.web.WorkflowActionMessage;

/**
 * 本地内存版 Inbox 消息记录。
 */
public class EmployeeWorkflowInboxMessage {
	private String eventId;
	private WorkflowActionMessage message;
	private EmployeeWorkflowInboxStatus status;
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

	public EmployeeWorkflowInboxStatus getStatus() {
		return status;
	}

	public void setStatus(EmployeeWorkflowInboxStatus status) {
		this.status = status;
	}

	public String getLastError() {
		return lastError;
	}

	public void setLastError(String lastError) {
		this.lastError = lastError;
	}
}
