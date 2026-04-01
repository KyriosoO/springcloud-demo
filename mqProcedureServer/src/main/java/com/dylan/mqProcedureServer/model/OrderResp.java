package com.dylan.mqProcedureServer.model;

public class OrderResp {
	public OrderResp(String orderId, String userId, String orderStatus) {
		this.orderId = orderId;
		this.userId = userId;
		this.orderStatus = orderStatus;
	}

	String orderId;
	String userId;
	String orderStatus;

	public String getOrderId() {
		return orderId;
	}

	public void setOrderId(String orderId) {
		this.orderId = orderId;
	}

	public String getUserId() {
		return userId;
	}

	public void setUserId(String userId) {
		this.userId = userId;
	}

	public String getOrderStatus() {
		return orderStatus;
	}

	public void setOrderStatus(String orderStatus) {
		this.orderStatus = orderStatus;
	}
}
