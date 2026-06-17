package com.dylan.workflow.web;

import com.dylan.workflow.model.WorkflowActionType;

/**
 * 工作流动作事件消息，供业务服务消费并执行领域逻辑。
 */
public class WorkflowActionMessage {
	private String eventId;
	private String actionName;
	private String processId;
	private String domain;
	private String businessId;
	private WorkflowActionType actionType;
	private Object payload;
	private String operator;

	public String getEventId() {
		return eventId;
	}

	public void setEventId(String eventId) {
		this.eventId = eventId;
	}

	public String getActionName() {
		return actionName;
	}

	public void setActionName(String actionName) {
		this.actionName = actionName;
	}

	public String getProcessId() {
		return processId;
	}

	public void setProcessId(String processId) {
		this.processId = processId;
	}

	public String getDomain() {
		return domain;
	}

	public void setDomain(String domain) {
		this.domain = domain;
	}

	public String getBusinessId() {
		return businessId;
	}

	public void setBusinessId(String businessId) {
		this.businessId = businessId;
	}

	public WorkflowActionType getActionType() {
		return actionType;
	}

	public void setActionType(WorkflowActionType actionType) {
		this.actionType = actionType;
	}

	public Object getPayload() {
		return payload;
	}

	public void setPayload(Object payload) {
		this.payload = payload;
	}

	public String getOperator() {
		return operator;
	}

	public void setOperator(String operator) {
		this.operator = operator;
	}
}
