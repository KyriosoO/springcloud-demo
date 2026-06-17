package com.dylan.workflow.engine;

import java.util.List;

/**
 * 多个动作分发器执行后的聚合异常。
 */
public class WorkflowActionDispatchException extends RuntimeException {
	private final List<String> failedDispatchers;

	public WorkflowActionDispatchException(List<String> failedDispatchers) {
		super("Workflow action dispatch failed: " + String.join(",", failedDispatchers));
		this.failedDispatchers = failedDispatchers;
	}

	public List<String> getFailedDispatchers() {
		return failedDispatchers;
	}
}
