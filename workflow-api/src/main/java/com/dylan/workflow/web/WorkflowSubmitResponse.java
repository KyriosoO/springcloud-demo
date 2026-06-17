package com.dylan.workflow.web;

public class WorkflowSubmitResponse {
	private String processId;

	public WorkflowSubmitResponse() {
	}

	public WorkflowSubmitResponse(String processId) {
		this.processId = processId;
	}

	public String getProcessId() {
		return processId;
	}

	public void setProcessId(String processId) {
		this.processId = processId;
	}
}
