package com.dylan.employee.model;

import java.util.Map;

/**
 * 员工域自己的待生效变更申请。
 */
public class EmployeeChangeRequest {
	/**
	 * 本地变更申请 ID。
	 */
	private String changeRequestId;
	private EmployeeChangeAction action;
	private EmployeeChangeStatus status;
	private String idCardNo;
	private Map<String, Object> employee;
	private String applicant;
	private String approvalProcessId;

	public String getChangeRequestId() {
		return changeRequestId;
	}

	public void setChangeRequestId(String changeRequestId) {
		this.changeRequestId = changeRequestId;
	}

	public EmployeeChangeAction getAction() {
		return action;
	}

	public void setAction(EmployeeChangeAction action) {
		this.action = action;
	}

	public EmployeeChangeStatus getStatus() {
		return status;
	}

	public void setStatus(EmployeeChangeStatus status) {
		this.status = status;
	}

	public String getIdCardNo() {
		return idCardNo;
	}

	public void setIdCardNo(String idCardNo) {
		this.idCardNo = idCardNo;
	}


	public Map<String, Object> getEmployee() {
		return employee;
	}

	public void setEmployee(Map<String, Object> employee) {
		this.employee = employee;
	}

	public String getApplicant() {
		return applicant;
	}

	public void setApplicant(String applicant) {
		this.applicant = applicant;
	}

	public String getApprovalProcessId() {
		return approvalProcessId;
	}

	public void setApprovalProcessId(String approvalProcessId) {
		this.approvalProcessId = approvalProcessId;
	}
}
