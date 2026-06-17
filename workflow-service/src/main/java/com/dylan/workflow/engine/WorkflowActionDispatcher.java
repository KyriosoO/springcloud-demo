package com.dylan.workflow.engine;

import com.dylan.workflow.model.WorkflowOutboxEvent;

public interface WorkflowActionDispatcher {
	String name();

	void dispatch(WorkflowOutboxEvent event);
}
