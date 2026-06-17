package com.dylan.workflow.engine;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.dylan.workflow.model.WorkflowOutboxEvent;

@Component
public class LoggingWorkflowActionDispatcher implements WorkflowActionDispatcher {
	private static final Logger log = LoggerFactory.getLogger(LoggingWorkflowActionDispatcher.class);

	@Override
	public String name() {
		return "log";
	}

	@Override
	public void dispatch(WorkflowOutboxEvent event) {
		log.info(
				"Workflow action ready to publish, eventId={}, actionName={}, processId={}, domain={}, businessId={}, actionType={}, operator={}",
				event.getEventId(), event.getMessage().getActionName(), event.getMessage().getProcessId(),
				event.getMessage().getDomain(), event.getMessage().getBusinessId(),
				event.getMessage().getActionType(), event.getMessage().getOperator());
	}
}
