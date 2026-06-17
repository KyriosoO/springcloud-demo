package com.dylan.order.api.model;

import java.io.Serializable;
import java.math.BigDecimal;
import java.time.LocalDateTime;

public class OrderMessage implements Serializable {
	private static final long serialVersionUID = -3263356767210103879L;
	private String orderId;
	private String userId;
	private String productId;
	private Integer quantity;
	private OrderStatus orderStatus;
	/**
	 * 交易金额，由前端创建订单时传入。Kryo 序列化依赖字段顺序，必须加在已有字段末尾。
	 */
	private BigDecimal amount;
	/**
	 * 订单创建时间，在 {@link #reset(String, String, String, int, BigDecimal, OrderStatus)}
	 * 中自动设置为当前时间。
	 */
	private LocalDateTime createdAt;

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

	public BigDecimal getAmount() {
		return amount;
	}

	public void setAmount(BigDecimal amount) {
		this.amount = amount;
	}

	public LocalDateTime getCreatedAt() {
		return createdAt;
	}

	public void setCreatedAt(LocalDateTime createdAt) {
		this.createdAt = createdAt;
	}

	public void reset(String orderId, String userId, String productId, int quantity, OrderStatus orderStatus) {
		this.orderId = orderId;
		this.userId = userId;
		this.productId = productId;
		this.quantity = quantity;
		this.orderStatus = orderStatus;
		this.amount = null;
		this.createdAt = LocalDateTime.now();
	}

	/**
	 * 新增签名：接收 amount 参数。createdAt 在方法内设为当前时间。
	 */
	public void reset(String orderId, String userId, String productId, int quantity, BigDecimal amount,
			OrderStatus orderStatus) {
		this.orderId = orderId;
		this.userId = userId;
		this.productId = productId;
		this.quantity = quantity;
		this.amount = amount;
		this.orderStatus = orderStatus;
		this.createdAt = LocalDateTime.now();
	}

	/**
	 * 深拷贝一份 OrderMessage，用于跨线程安全传递（如 MQ 异步发送到 Disruptor RingBuffer 外）。
	 * <p>RingBuffer 事件对象会在 publish 后被下游复用，因此跨线程使用前必须深拷贝。
	 */
	public OrderMessage copyForAsync() {
		OrderMessage copy = new OrderMessage();
		copy.orderId = this.orderId;
		copy.userId = this.userId;
		copy.productId = this.productId;
		copy.quantity = this.quantity;
		copy.orderStatus = this.orderStatus;
		copy.amount = this.amount;
		copy.createdAt = this.createdAt;
		return copy;
	}
}
