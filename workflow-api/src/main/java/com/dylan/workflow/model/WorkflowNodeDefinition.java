package com.dylan.workflow.model;

import java.util.ArrayList;
import java.util.List;

/**
 * 提交流程时传入的审批节点配置。
 */
public class WorkflowNodeDefinition {
	/**
	 * 节点唯一标识；为空时由服务端按顺序生成。
	 */
	private String nodeId;
	/**
	 * 节点展示名称，例如“审核”或“复核”。
	 */
	private String nodeName;
	/**
	 * 当前节点的审批策略：普通审批、会签或或签。
	 */
	private WorkflowApprovalType approvalType = WorkflowApprovalType.SINGLE;
	/**
	 * 当前节点允许审批的操作人；为空时不限制操作人。
	 */
	private List<String> approvers = new ArrayList<>();
	/**
	 * 当前节点通过后触发的业务动作。
	 */
	private String approveAction;
	/**
	 * 当前节点拒绝后触发的业务动作。
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
