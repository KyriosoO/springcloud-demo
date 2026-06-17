package com.dylan.workflow.model;

import java.util.ArrayList;
import java.util.List;

/**
 * 流程实例运行态，保存整体状态、当前节点和节点审批记录。
 */
public class WorkflowInstance {
	/**
	 * 流程实例 ID。
	 */
	private String processId;
	/**
	 * 业务类型，用于回调动作区分业务域。
	 */
	private String domain;
	
	/**
	 * 提交类型
	 */
	private String operationType;
	/**
	 * 业务主键。
	 */
	private String businessId;
	/**
	 * 提交后触发的动作名。
	 */
	private String submitAction;
	/**
	 * 流程整体状态。
	 */
	private WorkflowStatus status;
	/**
	 * 提交时的业务载荷。
	 */
	private Object payload;
	/**
	 * 最近一次操作人。
	 */
	private String operator;
	/**
	 * 当前待处理节点下标；流程结束时为 -1。
	 */
	private int currentNodeIndex = -1;
	/**
	 * 流程节点运行态列表。
	 */
	private List<WorkflowNodeInstance> nodes = new ArrayList<>();

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

	public String getOperationType() {
		return operationType;
	}

	public void setOperationType(String operationType) {
		this.operationType = operationType;
	}

	public String getBusinessId() {
		return businessId;
	}

	public void setBusinessId(String businessId) {
		this.businessId = businessId;
	}

	public String getSubmitAction() {
		return submitAction;
	}

	public void setSubmitAction(String submitAction) {
		this.submitAction = submitAction;
	}

	public WorkflowStatus getStatus() {
		return status;
	}

	public void setStatus(WorkflowStatus status) {
		this.status = status;
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

	public int getCurrentNodeIndex() {
		return currentNodeIndex;
	}

	public void setCurrentNodeIndex(int currentNodeIndex) {
		this.currentNodeIndex = currentNodeIndex;
	}

	public List<WorkflowNodeInstance> getNodes() {
		return nodes;
	}

	public void setNodes(List<WorkflowNodeInstance> nodes) {
		this.nodes = nodes;
	}
}
