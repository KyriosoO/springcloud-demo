package com.dylan.workflow.model;

/**
 * 创建流程实例的请求。
 */
public class WorkflowRequest {
	/**
	 * 业务类型，用于区分订单、员工资料等不同业务域。
	 */
	private String domain;
	
	/**
	 * 提交类型，用于区分流程
	 */
	private String operationType;
	/**
	 * 业务主键，供回调动作定位具体业务数据。
	 */
	private String businessId;
	/**
	 * 提交时附带的业务载荷，会随提交动作一起分发。
	 */
	private Object payload;
	/**
	 * 提交成功后触发的业务动作名称。
	 */
	private String submitAction;
	/**
	 * 发起人或当前操作者。
	 */
	private String operator;

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

	public Object getPayload() {
		return payload;
	}

	public void setPayload(Object payload) {
		this.payload = payload;
	}

	public String getSubmitAction() {
		return submitAction;
	}

	public void setSubmitAction(String submitAction) {
		this.submitAction = submitAction;
	}

	public String getOperator() {
		return operator;
	}

	public void setOperator(String operator) {
		this.operator = operator;
	}

}
