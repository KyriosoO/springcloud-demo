package com.dylan.workflow.web;

import java.util.ArrayList;
import java.util.List;

import com.dylan.workflow.model.WorkflowApprovalType;
import com.dylan.workflow.model.WorkflowNodeStatus;

/**
 * 流程详情中的节点快照。
 */
public class WorkflowNodeDetailResponse {
	private String nodeId;
	private String nodeName;
	private WorkflowApprovalType approvalType;
	private WorkflowNodeStatus status;
	private List<String> approvers = new ArrayList<>();
	private List<String> approvedOperators = new ArrayList<>();
	private List<String> rejectedOperators = new ArrayList<>();

	public String getNodeId() {
		return nodeId;
	}

	public void setNodeId(String nodeId) {
		this.nodeId = nodeId;
	}

	public String getNodeName() {
		return nodeName;
	}

	public void setNodeName(String nodeName) {
		this.nodeName = nodeName;
	}

	public WorkflowApprovalType getApprovalType() {
		return approvalType;
	}

	public void setApprovalType(WorkflowApprovalType approvalType) {
		this.approvalType = approvalType;
	}

	public WorkflowNodeStatus getStatus() {
		return status;
	}

	public void setStatus(WorkflowNodeStatus status) {
		this.status = status;
	}

	public List<String> getApprovers() {
		return approvers;
	}

	public void setApprovers(List<String> approvers) {
		this.approvers = approvers;
	}

	public List<String> getApprovedOperators() {
		return approvedOperators;
	}

	public void setApprovedOperators(List<String> approvedOperators) {
		this.approvedOperators = approvedOperators;
	}

	public List<String> getRejectedOperators() {
		return rejectedOperators;
	}

	public void setRejectedOperators(List<String> rejectedOperators) {
		this.rejectedOperators = rejectedOperators;
	}
}
