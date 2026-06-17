package com.dylan.workflow.model;

/**
 * 工作流动作 Outbox 事件投递状态。
 */
public enum WorkflowOutboxStatus {
	PENDING, DISPATCHED, FAILED
}
