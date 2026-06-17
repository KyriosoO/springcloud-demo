package com.dylan.workflow.web;

import com.dylan.workflow.model.WorkflowStatus;

/**
 * 我的待办列表项。
 */
public class WorkflowTodoResponse {
	private String todoId;
	private String processId;
	private String domain;
	private String operationType;
	private String businessId;
	private WorkflowStatus status;
	private Object payload;
	private int currentNodeIndex;
	private String currentNodeId;
	private String currentNodeName;

	public String getTodoId() {
		return todoId;
	}

	public void setTodoId(String todoId) {
		this.todoId = todoId;
	}

	public String getProcessId() {
		return processId;
	}

	public void setProcessId(String processId) {
		this.processId = processId;
	}

	public String getDomain() {
		return domain;
	}

	public void setDomain(String domain) {
		this.domain = domain;
	}

	public String getOperationType() {
		return operationType;
	}

	public void setOperationType(String operationType) {
		this.operationType = operationType;
	}

	public String getBusinessId() {
		return businessId;
	}

	public void setBusinessId(String businessId) {
		this.businessId = businessId;
	}

	public WorkflowStatus getStatus() {
		return status;
	}

	public void setStatus(WorkflowStatus status) {
		this.status = status;
	}

	public Object getPayload() {
		return payload;
	}

	public void setPayload(Object payload) {
		this.payload = payload;
	}

	public int getCurrentNodeIndex() {
		return currentNodeIndex;
	}

	public void setCurrentNodeIndex(int currentNodeIndex) {
		this.currentNodeIndex = currentNodeIndex;
	}

	public String getCurrentNodeId() {
		return currentNodeId;
	}

	public void setCurrentNodeId(String currentNodeId) {
		this.currentNodeId = currentNodeId;
	}

	public String getCurrentNodeName() {
		return currentNodeName;
	}

	public void setCurrentNodeName(String currentNodeName) {
		this.currentNodeName = currentNodeName;
	}
}
