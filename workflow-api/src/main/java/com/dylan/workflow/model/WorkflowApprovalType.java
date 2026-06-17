package com.dylan.workflow.model;

/**
 * 审批节点的通过策略。
 */
public enum WorkflowApprovalType {
	/**
	 * 普通审批：当前节点被任意一次同意操作通过。
	 */
	SINGLE,
	/**
	 * 会签：配置的所有审批人均同意后通过。
	 */
	COUNTERSIGN,
	/**
	 * 或签：配置的任一审批人同意后通过。
	 */
	OR_SIGN
}
