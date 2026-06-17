package com.dylan.workflow.engine;

public class WorkflowTodoChangedException extends RuntimeException {
	public WorkflowTodoChangedException(String message) {
		super(message);
	}
}
