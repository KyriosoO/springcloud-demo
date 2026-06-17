package com.dylan.mqprocedureserver.disruptor;

import java.math.BigDecimal;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;

import com.dylan.mqprocedureserver.model.OrderResp;
import com.dylan.order.api.model.OrderMessage;
import com.dylan.order.api.model.OrderStatus;

/**
 * Disruptor 环形队列事件，承载一次下单请求的全生命周期状态。
 * <p>事件对象在 RingBuffer 初始化时一次性分配（size=4096），
 * 下单过程中复用，每次 {@link #clear()} 重置所有字段，避免 GC。
 * <p>多生产者模式：秒杀场景下多个 HTTP 线程同时提交下单请求。
 */
public class OrderCreateEvent {
	// 输入
	private String userId;
	private String productId;
	private int quantity;
	private BigDecimal amount;

	// 中间状态（复用 OrderMessage 避免每次 new）
	private final OrderMessage orderMessage;

	// 输出
	private String orderId;
	private OrderResp response;
	private Throwable error;

	// 同步等待（使用 CompletableFuture，每次 clear() 后重新创建）
	private CompletableFuture<OrderResp> future;

	public OrderCreateEvent() {
		this.orderMessage = new OrderMessage();
		this.future = new CompletableFuture<>();
	}

	/**
	 * 重置事件对象供下次复用。不创建任何新对象（CompletableFuture 除外）。
	 * <p>future 必须重新创建，因为已完成的 CompletableFuture 无法重置。
	 */
	void clear() {
		this.userId = null;
		this.productId = null;
		this.quantity = 0;
		this.amount = null;
		this.orderMessage.reset(null, null, null, 0, (BigDecimal) null, (OrderStatus) null);
		this.orderId = null;
		this.response = null;
		this.error = null;
		this.future = new CompletableFuture<>();
	}

	// -- getters/setters --

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

	public int getQuantity() {
		return quantity;
	}

	public void setQuantity(int quantity) {
		this.quantity = quantity;
	}

	public BigDecimal getAmount() {
		return amount;
	}

	public void setAmount(BigDecimal amount) {
		this.amount = amount;
	}

	public OrderMessage getOrderMessage() {
		return orderMessage;
	}

	public String getOrderId() {
		return orderId;
	}

	public void setOrderId(String orderId) {
		this.orderId = orderId;
	}

	public OrderResp getResponse() {
		return response;
	}

	public void setResponse(OrderResp response) {
		this.response = response;
	}

	public Throwable getError() {
		return error;
	}

	public void setError(Throwable error) {
		this.error = error;
	}

	public CompletableFuture<OrderResp> getFuture() {
		return future;
	}
}
