package com.dylan.workflow.model;

/**
 * 流程实例的整体状态。
 */
public enum WorkflowStatus {
	/**
	 * 已提交，正在等待当前审批节点处理。
	 */
	SUBMITTED,
	/**
	 * 所有审批节点均已通过。
	 */
	APPROVED,
	/**
	 * 任一节点被拒绝后，流程进入终态。
	 */
	REJECTED
}
