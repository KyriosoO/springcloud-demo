package com.dylan.workflow.model;

/**
 * 单个审批节点的处理状态。
 */
public enum WorkflowNodeStatus {
	/**
	 * 节点等待审批。
	 */
	PENDING,
	/**
	 * 节点已通过。
	 */
	APPROVED,
	/**
	 * 节点已拒绝。
	 */
	REJECTED
}
