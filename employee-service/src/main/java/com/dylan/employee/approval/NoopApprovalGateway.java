package com.dylan.employee.approval;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import com.dylan.employee.model.EmployeeChangeRequest;

/**
 * 无审批实现，用于快速拔掉工作流。
 */
@Component
@ConditionalOnProperty(name = "employee.approval.mode", havingValue = "none")
public class NoopApprovalGateway implements ApprovalGateway {
	@Override
	public String submit(EmployeeChangeRequest request) {
		return "NO_APPROVAL";
	}
}
