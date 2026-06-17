package com.dylan.mqprocedureserver.disruptor;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.concurrent.atomic.AtomicLong;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import com.dylan.common.redis.service.RedisService;
import com.dylan.mqprocedureserver.model.OrderResp;
import com.dylan.mqprocedureserver.support.CreateOrderSupport;
import com.dylan.order.api.model.OrderMessage;
import com.lmax.disruptor.EventHandler;

/**
 * Disruptor EventHandler，将下单拆分为三个阶段。
 * <p>阶段 1：库存检查 + 订单 ID 生成 + OrderMessage 初始化 + Redis 写入
 * <p>阶段 2：MQ 异步发送（通过独立线程池 {@link OrderMqAsyncExecutor}，避免阻塞 RingBuffer 线程）
 * <p>阶段 3：构造 OrderResp 并通过 CompletableFuture 返回给调用方
 * <p>处理完成后调用 {@link OrderCreateEvent#clear()} 归还可复用对象。
 */
@Component
public class OrderCreateEventHandler implements EventHandler<OrderCreateEvent> {
	private static final Logger log = LoggerFactory.getLogger(OrderCreateEventHandler.class);
	private static final AtomicLong ORDER_SEQ = new AtomicLong(System.currentTimeMillis());

	private final RedisService redisService;
	private final CreateOrderSupport orderSupport;
	private final OrderMqAsyncExecutor mqExecutor;

	public OrderCreateEventHandler(RedisService redisService, CreateOrderSupport orderSupport,
			OrderMqAsyncExecutor mqExecutor) {
		this.redisService = redisService;
		this.orderSupport = orderSupport;
		this.mqExecutor = mqExecutor;
	}

	@Override
	public void onEvent(OrderCreateEvent event, long sequence, boolean endOfBatch) {
		try {
			// 阶段 1：库存 + 订单 ID + 组装 OrderMessage + Redis 写
			if (null == redisService.get("stock:1001")) {
				redisService.set("stock:1001", 20); // 模拟库存
			}
			String orderId = "O" + ORDER_SEQ.getAndIncrement();
			OrderMessage order = event.getOrderMessage();
			order.reset(orderId, event.getUserId(), event.getProductId(),
					event.getQuantity(), event.getAmount(), null);
			order.setCreatedAt(LocalDateTime.now());
			event.setOrderId(orderId);
			orderSupport.saveOrderToRedis(order);

			// 阶段 2：MQ 异步发送（深拷贝 ringBuffer 对象后投递到独立线程池）
			// 不使用 CompletableFuture.runAsync()，避免污染共用 ForkJoinPool
			OrderMessage snapshot = order.copyForAsync();
			mqExecutor.execute(() -> {
				try {
					orderSupport.sendOrderCreateMq(snapshot);
				} catch (Exception e) {
					log.warn("order mq send failed orderId={}", orderId, e);
					orderSupport.markMqSendFail(orderId);
				}
			});

			// 阶段 3：构建响应并通过 CompletableFuture 返回
			OrderResp resp = orderSupport.buildAcceptedResp(order);
			event.setResponse(resp);
			event.getFuture().complete(resp);
		} catch (Exception e) {
			log.error("order create failed userId={} productId={}", event.getUserId(), event.getProductId(), e);
			event.setError(e);
			event.getFuture().completeExceptionally(e);
		} finally {
			// 归还可复用对象，避免状态污染下次使用
			event.clear();
		}
	}
}
