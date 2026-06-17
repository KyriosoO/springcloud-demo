package com.dylan.employee.web;

/**
 * 员工变更提交审批后的响应。
 */
public class EmployeeChangeSubmitResponse {
	private String changeRequestId;
	private String processId;

	public EmployeeChangeSubmitResponse() {
	}

	public EmployeeChangeSubmitResponse(String changeRequestId, String processId) {
		this.changeRequestId = changeRequestId;
		this.processId = processId;
	}

	public String getChangeRequestId() {
		return changeRequestId;
	}

	public void setChangeRequestId(String changeRequestId) {
		this.changeRequestId = changeRequestId;
	}

	public String getProcessId() {
		return processId;
	}

	public void setProcessId(String processId) {
		this.processId = processId;
	}
}
