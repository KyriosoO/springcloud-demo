package com.dylan.mqprocedureserver.disruptor;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.util.concurrent.CompletableFuture;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.dylan.common.redis.service.RedisService;
import com.dylan.mqprocedureserver.model.OrderResp;
import com.dylan.mqprocedureserver.support.CreateOrderSupport;
import com.dylan.order.api.model.OrderMessage;

/**
 * CreateOrderDisruptor 单元测试，覆盖事件发布、Handler 处理、异常 fallback 和资源清理。
 */
class CreateOrderDisruptorTest {

	private CreateOrderDisruptor disruptor;
	private RedisService redisService;
	private CreateOrderSupport orderSupport;
	private OrderMqAsyncExecutor mqExecutor;

	@BeforeEach
	void setUp() {
		redisService = mock(RedisService.class);
		orderSupport = mock(CreateOrderSupport.class);
		mqExecutor = mock(OrderMqAsyncExecutor.class);
		when(redisService.get("stock:1001")).thenReturn(null);

		OrderCreateEventHandler handler = new OrderCreateEventHandler(redisService, orderSupport, mqExecutor);
		disruptor = new CreateOrderDisruptor(handler);
	}

	@AfterEach
	void tearDown() throws Exception {
		if (disruptor != null) {
			disruptor.destroy();
		}
	}

	@Test
	void publishAndCompleteSuccessfully() throws Exception {
		doNothing().when(orderSupport).saveOrderToRedis(any());
		when(orderSupport.buildAcceptedResp(any())).thenReturn(new OrderResp("O-1", "user1", "订单已受理，处理中.."));

		// 模拟 MQ executor 同步执行任务
		doAnswer(inv -> {
			Runnable runnable = inv.getArgument(0);
			runnable.run();
			return null;
		}).when(mqExecutor).execute(any(Runnable.class));

		OrderResp resp = disruptor.createOrder("user1", "P1", 1, new BigDecimal("99.99"));

		assertNotNull(resp);
		assertEquals("O-1", resp.getOrderId());
		assertEquals("user1", resp.getUserId());

		verify(orderSupport).saveOrderToRedis(any(OrderMessage.class));
		verify(orderSupport).buildAcceptedResp(any(OrderMessage.class));
		verify(mqExecutor).execute(any(Runnable.class));
	}

	@Test
	void handlerSavesOrderToRedis() throws Exception {
		doNothing().when(orderSupport).saveOrderToRedis(any());
		when(orderSupport.buildAcceptedResp(any())).thenReturn(new OrderResp("O-1", "user1", "OK"));

		doAnswer(inv -> {
			((Runnable) inv.getArgument(0)).run();
			return null;
		}).when(mqExecutor).execute(any(Runnable.class));

		disruptor.createOrder("user1", "P1", 1, new BigDecimal("100"));

		verify(orderSupport).saveOrderToRedis(any(OrderMessage.class));
	}

	@Test
	void handlerSendsMqAfterSave() throws Exception {
		doNothing().when(orderSupport).saveOrderToRedis(any());
		// 使用 copyForAsync 返回的 snapshot 作为 MQ payload
		when(orderSupport.buildAcceptedResp(any())).thenReturn(new OrderResp("O-1", "user1", "OK"));

		// MQ executor 需要接收 Runnable 并执行
		CompletableFuture<Boolean> mqCalled = new CompletableFuture<>();
		doAnswer(inv -> {
			Runnable r = inv.getArgument(0);
			r.run();
			mqCalled.complete(true);
			return null;
		}).when(mqExecutor).execute(any(Runnable.class));

		disruptor.createOrder("user1", "P1", 1, new BigDecimal("200"));

		assertTrue(mqCalled.get(), "MQ send should be triggered after save");
		verify(mqExecutor).execute(any(Runnable.class));
	}

	@Test
	void handlerCompletesFutureExceptionallyOnSaveError() {
		doThrow(new RuntimeException("Redis unavailable")).when(orderSupport).saveOrderToRedis(any());

		try {
			disruptor.createOrder("user1", "P1", 1, new BigDecimal("300"));
			fail("Expected RuntimeException");
		} catch (Exception e) {
			assertTrue(e instanceof RuntimeException);
			assertTrue(e.getMessage().contains("order create failed")
					|| e.getMessage().contains("Redis unavailable"));
		}
	}

	@Test
	void eventClearResetsStateAfterProcessing() throws Exception {
		doNothing().when(orderSupport).saveOrderToRedis(any());
		when(orderSupport.buildAcceptedResp(any()))
				.thenReturn(new OrderResp("O-A", "userA", "OK"))
				.thenReturn(new OrderResp("O-B", "userB", "OK"));

		doAnswer(inv -> {
			((Runnable) inv.getArgument(0)).run();
			return null;
		}).when(mqExecutor).execute(any(Runnable.class));

		// 第一次下单
		OrderResp first = disruptor.createOrder("user1", "P1", 1, new BigDecimal("100"));
		assertNotNull(first);
		assertEquals("userA", first.getUserId());

		// 第二次下单 — 验证 clear() 后状态正确重置
		OrderResp second = disruptor.createOrder("user2", "P2", 2, new BigDecimal("200"));
		assertEquals("userB", second.getUserId());
	}
}
