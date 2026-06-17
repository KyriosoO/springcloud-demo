package com.dylan.workflow.web;

public class WorkflowOperationRequest {
	private String operator;
	private String todoId;

	public String getOperator() {
		return operator;
	}

	public void setOperator(String operator) {
		this.operator = operator;
	}

	public String getTodoId() {
		return todoId;
	}

	public void setTodoId(String todoId) {
		this.todoId = todoId;
	}
}
