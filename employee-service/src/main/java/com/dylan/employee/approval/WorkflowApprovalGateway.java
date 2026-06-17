package com.dylan.employee.approval;

import java.util.Map;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

import com.dylan.employee.model.EmployeeChangeAction;
import com.dylan.employee.model.EmployeeChangeRequest;
import com.dylan.workflow.model.WorkflowRequest;

/**
 * workflow-service 审批网关实现。
 */
@Component
@ConditionalOnProperty(name = "employee.approval.mode", havingValue = "workflow", matchIfMissing = true)
public class WorkflowApprovalGateway implements ApprovalGateway {
	private static final String BUSINESS_TYPE_CREATE = "create";
	private static final String BUSINESS_TYPE_UPDATE = "update";

	private final WorkflowClient workflowClient;

	public WorkflowApprovalGateway(WorkflowClient workflowClient) {
		this.workflowClient = workflowClient;
	}

	@Override
	public String submit(EmployeeChangeRequest request) {
		WorkflowRequest workflowRequest = new WorkflowRequest();
		workflowRequest.setDomain("employee");
		workflowRequest.setOperationType(request.getAction() == EmployeeChangeAction.CREATE ? BUSINESS_TYPE_CREATE
				: BUSINESS_TYPE_UPDATE);
		workflowRequest.setBusinessId(request.getChangeRequestId());
		workflowRequest.setOperator(request.getApplicant());
		workflowRequest.setPayload(request.getEmployee());
		return workflowClient.submit(workflowRequest).getProcessId();
	}
}
