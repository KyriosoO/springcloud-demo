package com.dylan.workflow.support;

public record WorkflowTodoToken(int version, String processId, int currentNodeIndex, String currentNodeId,
		String operator) {
}
