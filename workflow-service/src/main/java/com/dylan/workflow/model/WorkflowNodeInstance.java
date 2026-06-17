package com.dylan.workflow.model;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;

/**
 * 流程实例中的审批节点运行态。
 */
public class WorkflowNodeInstance {
	/**
	 * 节点唯一标识，用于前端或业务侧定位当前审批环节。
	 */
	private String nodeId;
	/**
	 * 节点展示名称，例如“审核”或“复核”。
	 */
	private String nodeName;
	/**
	 * 节点审批策略，决定一次同意是否足以推进流程。
	 */
	private WorkflowApprovalType approvalType = WorkflowApprovalType.SINGLE;
	/**
	 * 节点允许审批人；为空表示不限制审批人。
	 */
	private List<String> approvers = new ArrayList<>();
	/**
	 * 已同意的操作人集合，使用 Set 避免同一人重复计数。
	 */
	private Set<String> approvedOperators = new LinkedHashSet<>();
	/**
	 * 已拒绝的操作人集合。
	 */
	private Set<String> rejectedOperators = new LinkedHashSet<>();
	/**
	 * 当前节点状态。
	 */
	private WorkflowNodeStatus status = WorkflowNodeStatus.PENDING;
	/**
	 * 节点通过后触发的动作名。
	 */
	private String approveAction;
	/**
	 * 节点拒绝后触发的动作名。
	 */
	private String rejectAction;

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

	public List<String> getApprovers() {
		return approvers;
	}

	public void setApprovers(List<String> approvers) {
		this.approvers = approvers;
	}

	public Set<String> getApprovedOperators() {
		return approvedOperators;
	}

	public void setApprovedOperators(Set<String> approvedOperators) {
		this.approvedOperators = approvedOperators;
	}

	public Set<String> getRejectedOperators() {
		return rejectedOperators;
	}

	public void setRejectedOperators(Set<String> rejectedOperators) {
		this.rejectedOperators = rejectedOperators;
	}

	public WorkflowNodeStatus getStatus() {
		return status;
	}

	public void setStatus(WorkflowNodeStatus status) {
		this.status = status;
	}

	public String getApproveAction() {
		return approveAction;
	}

	public void setApproveAction(String approveAction) {
		this.approveAction = approveAction;
	}

	public String getRejectAction() {
		return rejectAction;
	}

	public void setRejectAction(String rejectAction) {
		this.rejectAction = rejectAction;
	}
}
