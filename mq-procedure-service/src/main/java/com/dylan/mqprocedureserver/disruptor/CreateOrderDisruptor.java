package com.dylan.mqprocedureserver.disruptor;

import java.math.BigDecimal;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicInteger;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.stereotype.Component;

import com.dylan.mqprocedureserver.model.OrderResp;
import com.lmax.disruptor.BlockingWaitStrategy;
import com.lmax.disruptor.dsl.Disruptor;
import com.lmax.disruptor.dsl.ProducerType;

/**
 * 下单 Disruptor 封装，管理 RingBuffer 生命周期并提供同步下单接口。
 * <p>多生产者模式（ProducerType.MULTI）：秒杀场景多个 HTTP 线程并发提交。
 * <p>RingBuffer size = 4096，预分配 OrderCreateEvent[4096]，启动后不再创建新事件对象。
 * <p>下单语义为同步阻塞（客户端等待响应），通过
 * {@link OrderCreateEvent#getFuture()} 的 CompletableFuture 实现。
 * <p>MQ 异步发送由独立的 {@link OrderMqAsyncExecutor} 线程池执行，
 * 不阻塞 Disruptor RingBuffer 线程。
 */
@Component
public class CreateOrderDisruptor implements DisposableBean {
	private static final Logger log = LoggerFactory.getLogger(CreateOrderDisruptor.class);
	private static final int RING_BUFFER_SIZE = 4096;
	private static final long CREATE_TIMEOUT_SECONDS = 30;

	private final Disruptor<OrderCreateEvent> disruptor;

	public CreateOrderDisruptor(OrderCreateEventHandler handler) {
		ThreadFactory threadFactory = new ThreadFactory() {
			private final AtomicInteger counter = new AtomicInteger(1);

			@Override
			public Thread newThread(Runnable r) {
				Thread t = new Thread(r, "order-create-disruptor-" + counter.getAndIncrement());
				t.setDaemon(true);
				return t;
			}
		};
		this.disruptor = new Disruptor<>(
				OrderCreateEvent::new,
				RING_BUFFER_SIZE,
				threadFactory,
				ProducerType.MULTI,
				new BlockingWaitStrategy());
		// 单 Handler 串行处理，不引入多阶段 EventHandler 链
		this.disruptor.handleEventsWith(handler);
		this.disruptor.start();
		log.info("CreateOrderDisruptor started ringBufferSize={} producerType=MULTI", RING_BUFFER_SIZE);
	}

	/**
	 * 同步下单：通过 RingBuffer.next() 获取 slot → 填入数据 → publish → 等待 EventHandler 完成。
	 *
	 * @param userId    用户 ID
	 * @param productId 商品 ID
	 * @param quantity  数量
	 * @param amount    金额
	 * @return 下单响应，含 orderId
	 * @throws RuntimeException 下单超时或处理异常
	 */
	public OrderResp createOrder(String userId, String productId, int quantity, BigDecimal amount) {
		long sequence = disruptor.getRingBuffer().next();
		try {
			OrderCreateEvent event = disruptor.getRingBuffer().get(sequence);
			event.setUserId(userId);
			event.setProductId(productId);
			event.setQuantity(quantity);
			event.setAmount(amount);
			CompletableFuture<OrderResp> future = event.getFuture();
			disruptor.getRingBuffer().publish(sequence);
			return future.get(CREATE_TIMEOUT_SECONDS, TimeUnit.SECONDS);
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			throw new RuntimeException("order create interrupted", e);
		} catch (ExecutionException e) {
			Throwable cause = e.getCause();
			if (cause instanceof RuntimeException re) {
				throw re;
			}
			throw new RuntimeException("order create failed", cause);
		} catch (TimeoutException e) {
			throw new RuntimeException("order create timeout after " + CREATE_TIMEOUT_SECONDS + "s", e);
		}
	}

	@Override
	public void destroy() throws Exception {
		log.info("CreateOrderDisruptor shutting down");
		disruptor.shutdown(1, TimeUnit.SECONDS);
	}
}
