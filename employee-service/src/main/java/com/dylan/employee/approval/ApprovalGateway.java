package com.dylan.employee.approval;

import com.dylan.employee.model.EmployeeChangeRequest;

/**
 * 审批能力网关，隔离具体工作流实现。
 */
public interface ApprovalGateway {
	String submit(EmployeeChangeRequest request);
}
