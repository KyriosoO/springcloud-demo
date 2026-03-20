package com.dylan.common.model.order;

public class OrderResult {
	private String orderId;

	// SUCCESS / FAILED
	private OrderStatus status;

	private String reason;

	public OrderResult() {
	}

	public OrderResult(String orderId, String status) {
		this.orderId = orderId;
		this.status = OrderStatus.valueOf(status);
	}

	public OrderResult(String orderId, String status, String reason) {
		this.orderId = orderId;
		this.status = OrderStatus.valueOf(status);
		;
		this.reason = reason;
	}

	public String getOrderId() {
		return orderId;
	}

	public void setOrderId(String orderId) {
		this.orderId = orderId;
	}

	public String getStatus() {
		if (null == status) {
			return "";
		}
		return status.toString();
	}

	public void setStatus(String status) {
		if (null != status && !status.isEmpty()) {
			this.status = OrderStatus.valueOf(status);
		}
	}

	public String getReason() {
		return reason;
	}

	public void setReason(String reason) {
		this.reason = reason;
	}

}
