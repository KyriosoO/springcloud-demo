package com.dylan.workflow.web;

import java.util.ArrayList;
import java.util.List;

import com.dylan.workflow.model.WorkflowStatus;

/**
 * 流程详情响应。
 */
public class WorkflowDetailResponse {
	private String processId;
	private String domain;
	private String operationType;
	private String businessId;
	private WorkflowStatus status;
	private String operator;
	/**
	 * 提交时携带的业务数据，用于详情页展示业务信息。
	 */
	private Object payload;
	/**
	 * 当前待处理节点的下标；流程结束时为 -1。
	 */
	private int currentNodeIndex;
	/**
	 * 当前待处理节点的标识；流程结束时为空。
	 */
	private String currentNodeId;
	/**
	 * 全部节点的审批状态和审批记录。
	 */
	private List<WorkflowNodeDetailResponse> nodes = new ArrayList<>();

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

	public WorkflowStatus getStatus() {
		return status;
	}

	public void setStatus(WorkflowStatus status) {
		this.status = status;
	}

	public String getOperator() {
		return operator;
	}

	public void setOperator(String operator) {
		this.operator = operator;
	}

	public Object getPayload() {
		return payload;
	}

	public void setPayload(Object payload) {
		this.payload = payload;
	}

	public int getCurrentNodeIndex() {
		return currentNodeIndex;
	}

	public void setCurrentNodeIndex(int currentNodeIndex) {
		this.currentNodeIndex = currentNodeIndex;
	}

	public String getCurrentNodeId() {
		return currentNodeId;
	}

	public void setCurrentNodeId(String currentNodeId) {
		this.currentNodeId = currentNodeId;
	}

	public List<WorkflowNodeDetailResponse> getNodes() {
		return nodes;
	}

	public void setNodes(List<WorkflowNodeDetailResponse> nodes) {
		this.nodes = nodes;
	}
}
