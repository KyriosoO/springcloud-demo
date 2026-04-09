package com.dylan.common.model.order;

import java.io.Serializable;

public class OrderMessage implements Serializable {
	/**
	 * 
	 */
	private static final long serialVersionUID = -3263356767210103879L;
	private String orderId;
	private String userId;
	private String productId;
	private Integer quantity;
	private OrderStatus orderStatus;

	public OrderMessage() {
	}

	public OrderMessage(String orderId, String userId, String productId, Integer quantity, String orderStatus) {
		this.orderId = orderId;
		this.userId = userId;
		this.productId = productId;
		this.quantity = quantity;
		this.orderStatus = OrderStatus.valueOf(orderStatus);
	}

	public OrderMessage(String orderId, Integer quantity) {
		this.orderId = orderId;
		this.quantity = quantity;
	}

	public String getOrderId() {
		return orderId;
	}

	public void setOrderId(String orderId) {
		this.orderId = orderId;
	}

	public Integer getQuantity() {
		return quantity;
	}

	public void setQuantity(Integer quantity) {
		this.quantity = quantity;
	}

	public String getUserId() {
		return userId;
	}

	public void setUserId(String userId) {
		this.userId = userId;
	}

	public String getProductId() {
		return productId;
	}

	public void setProductId(String productId) {
		this.productId = productId;
	}

	public String getOrderStatus() {
		if (null == orderStatus) {
			return "";
		}
		return orderStatus.toString();
	}

	public void setOrderStatus(String orderStatus) {
		if (null != orderStatus && !orderStatus.isEmpty()) {
			this.orderStatus = OrderStatus.valueOf(orderStatus);
		}
	}

	public void reset(String orderId, String userId, String productId, int quantity, OrderStatus orderStatus) {
		this.orderId = orderId;
		this.userId = userId;
		this.productId = productId;
		this.quantity = quantity;
		this.orderStatus = orderStatus;
	}
}